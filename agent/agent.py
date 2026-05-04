import os
import json
from anthropic import Anthropic
from dotenv import load_dotenv

from agent.tools import TOOL_REGISTRY
from prompts.research_note import SYSTEM_PROMPT
from agent.utils import call_with_retry

# Build the cached system prompt block once at module level.
# This structure tells Claude to cache this content after the first call.
# All subsequent calls in the same session read from cache at ~90% lower cost.
CACHED_SYSTEM_PROMPT = [
    {
        "type": "text",
        "text": SYSTEM_PROMPT,
        "cache_control": {"type": "ephemeral"}
    }
]

load_dotenv()

# Hard cap on tool calls per run.
# Prevents infinite loops and controls API spend.
MAX_ITERATIONS = 10

def build_tool_definitions() -> list[dict]:
    """
    Generates Claude-compatible tool definitions from our Pydantic input schemas.
    Claude reads these to know what tools exist and what arguments they accept.
    """
    tools = []

    for tool_name, (func, input_model) in TOOL_REGISTRY.items():
        # Pydantic v2 generates a JSON schema from the model.
        # This is exactly what Claude needs for tool definitions.
        schema = input_model.model_json_schema()

        tools.append({
            "name": tool_name,
            "description": func.__doc__ or f"Tool: {tool_name}",
            "input_schema": {
                "type": "object",
                "properties": schema.get("properties", {}),
                "required": schema.get("required", []),
            }
        })

    return tools

def execute_tool(tool_name: str, tool_input: dict) -> str:
    """
    Looks up a tool by name, validates its input, executes it,
    and returns the result as a JSON string for Claude to read.
    """
    if tool_name not in TOOL_REGISTRY:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    func, input_model = TOOL_REGISTRY[tool_name]

    try:
        # Validate arguments against the Pydantic input schema.
        # If Claude passes malformed arguments, this raises a
        # ValidationError here rather than inside the tool function.
        validated_input = input_model(**tool_input)
        result = func(validated_input)

        # Convert Pydantic output model to a JSON string.
        # This is what gets appended to the conversation as a tool_result.
        return result.model_dump_json(indent=2)

    except Exception as e:
        # Return a structured error so Claude can reason about the failure
        # rather than seeing a raw Python traceback.
        return json.dumps({"error": str(e), "tool": tool_name})
    
def run_research_agent(ticker: str) -> str:
    """
    Runs the finance research agent for a given ticker.
    Returns a structured research note as a string.
    """
    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    tool_definitions = build_tool_definitions()

    # Initial message: the user request that starts the agent loop.
    messages = [
        {
            "role": "user",
            "content": (
                f"Produce a complete research note for {ticker.upper()}. "
                f"Use all available tools to gather data. "
                f"Every claim must be cited."
            )
        }
    ]

    print(f"\n[Agent] Starting research for {ticker.upper()}")
    iteration = 0

    while iteration < MAX_ITERATIONS:
        iteration += 1
        print(f"[Agent] Iteration {iteration}/{MAX_ITERATIONS}")

        # Call the Claude API with the current message history and tool definitions.
        response = call_with_retry(
            client,
            model="claude-sonnet-4-5",
            max_tokens=8096,
            system=CACHED_SYSTEM_PROMPT,
            tools=tool_definitions,
            messages=messages,
            betas=["prompt-caching-2024-07-31"],
        )

        print(f"[Agent] Stop reason: {response.stop_reason}")

        # Append Claude's response to the message history.
        messages.append({
            "role": "assistant",
            "content": response.content
        })

        # If Claude is done, extract and return the final text response.
        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    text = block.text
                    # Strip any preamble before the first markdown heading.
                    # Claude sometimes thinks out loud before writing the note.
                    # The actual report always starts with a # or ## heading.
                    heading_index = -1
                    for marker in ["# ", "## "]:
                        idx = text.find(marker)
                        if idx != -1:
                            if heading_index == -1 or idx < heading_index:
                                heading_index = idx
                    if heading_index > 0:
                        text = text[heading_index:]
                    print(f"[Agent] Research note complete. Length: {len(text)} chars")
                    return text
            return "Agent completed but produced no text output."

        # If Claude wants to call tools, execute each one.
        if response.stop_reason == "tool_use":
            tool_results = []

            for block in response.content:
                if block.type == "tool_use":
                    print(f"[Agent] Tool call: {block.name} | Input: {json.dumps(block.input)[:100]}...")
                    result = execute_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

            # Append all tool results as a user message.
            # This is the correct Messages API pattern:
            # tool results go in the user turn, not the assistant turn.
            messages.append({
                "role": "user",
                "content": tool_results
            })

        else:
            # Unexpected stop reason. Break to avoid an infinite loop.
            print(f"[Agent] Unexpected stop reason: {response.stop_reason}. Stopping.")
            break

    return "Agent reached maximum iterations without completing the research note."

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    result = run_research_agent("AAPL")
    print("\n" + "="*60)
    print(result)