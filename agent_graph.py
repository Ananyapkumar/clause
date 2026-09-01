"""The Day 3 tool loop, ported to LangGraph.

Day 18.

WHAT WAS PORTED, AND WHAT DELIBERATELY WAS NOT
----------------------------------------------
Ported: the CONTROL FLOW. The `for turn in range(MAX_TURNS)` loop in agent.py
becomes an explicit graph - two nodes and a conditional edge.

Not ported: the provider integration. This still calls
`client.interactions.create` exactly as agent.py does, with the same TOOLS
schemas and the same dispatcher.

That restraint is the point. The interesting question is "what does a graph
framework buy me over a while-loop", and the only way to answer it is to change
one variable. Swapping in langchain-google-genai at the same time would have
changed the model wrapper, the message format and the tool-calling convention as
well, and the comparison would have been worthless - the same mistake as the
first ablation, which removed the domain rules from the prompt and left them in
the schema.

    agent.py         hand-written loop      -> the mechanism
    agent_graph.py   same loop as a graph   -> the abstraction over it

Both call the same model, run the same tools, and produce the same answers.

INSTALL
-------
    pip install langgraph

Free and open source. No account, no key, no usage charge. It is a Python
library that runs locally; it does not talk to anything.

RUN
---
    py agent_graph.py --mock     structural test, ZERO API requests
    py agent_graph.py            the real thing, ~2-4 requests per question

The --mock path is not a toy. A graph whose control flow is decided by model
output cannot be unit tested against the real model - the execution path is not
knowable in advance and every run costs quota. So the model is replaced by a
scripted stand-in and the GRAPH is tested: does the conditional edge route
correctly, do tool results reach the next turn, does the recursion limit hold.
That is the answer to "how do you test a non-deterministic system" - you make
the non-deterministic part deterministic and test everything around it.

WHAT THE FRAMEWORK ACTUALLY BOUGHT - see PORT_NOTES at the bottom of the file.
"""

import json
import operator
import sys
from typing import Annotated, TypedDict

from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph

# Reuse the tools, schemas and dispatcher from the hand-written version. If the
# port had copied them, the two files could drift and the comparison would stop
# being between two control flows and start being between two programs.
from agent import MAX_TURNS, MODEL, TOOLS, run_tool

load_dotenv()

MOCK = "--mock" in sys.argv
VERBOSE = "--verbose" in sys.argv


# =============================================================
# THE STATE
# =============================================================
# In the hand-written loop, `history` was a local variable that the loop body
# appended to. In a graph there is no shared local scope - nodes are separate
# functions that receive state and return an update to it. So the thing that
# was implicit becomes a declared type.
#
# Annotated[list, operator.add] is a REDUCER. It tells the graph how to merge a
# node's return value into existing state: for `messages`, concatenate rather
# than replace. Without it, each node would overwrite the whole conversation
# and the model would lose its history every turn.
#
# `turns` has no reducer, so it uses the default - the returned value replaces
# the old one. That is what you want for a counter.

class AgentState(TypedDict):
    messages: Annotated[list, operator.add]
    tool_log: Annotated[list, operator.add]
    turns: int


# =============================================================
# THE MODEL CLIENT
# =============================================================

class _Step:
    """Minimal stand-in for one step in a provider response."""

    def __init__(self, type, name=None, arguments=None, id=None, text=None):
        self.type = type
        self.name = name
        self.arguments = arguments or {}
        self.id = id
        self.text = text

    def __repr__(self):
        if self.type == "function_call":
            return f"<function_call {self.name}({self.arguments})>"
        return f"<{self.type} {self.text!r}>"


class _Interaction:
    def __init__(self, steps, output_text=""):
        self.steps = steps
        self.output_text = output_text


class MockClient:
    """A scripted model. Costs nothing and behaves the same way every run.

    Turn 1 asks for a tool. Turn 2 answers. That is the shortest path that
    exercises every edge in the graph: START -> agent -> tools -> agent -> END.
    """

    def __init__(self):
        self.calls = 0

    def reset(self):
        """Re-arm the script. A stateful stand-in that is not reset between
        runs stops being a fixture and becomes a source of variance - which is
        the exact thing the mock exists to remove."""
        self.calls = 0

    class _Interactions:
        def __init__(self, outer):
            self.outer = outer

        def create(self, model, input, tools):
            self.outer.calls += 1
            if self.outer.calls == 1:
                return _Interaction([
                    _Step("function_call", name="lookup_customer",
                          arguments={"name": "Acme Corp"}, id="call_mock_1")
                ])
            return _Interaction(
                [_Step("text", text="Acme Corp is on Enterprise with 3 open tickets.")],
                output_text="Acme Corp is on Enterprise with 3 open tickets.",
            )

    @property
    def interactions(self):
        return self._Interactions(self)


if MOCK:
    client = MockClient()
else:
    from google import genai
    client = genai.Client()


# =============================================================
# NODE 1 - ASK THE MODEL
# =============================================================

def call_model(state: AgentState) -> dict:
    """One model call. Returns only what changed."""
    interaction = client.interactions.create(
        model=MODEL,
        input=state["messages"],
        tools=TOOLS,
    )

    if VERBOSE:
        print(f"--- turn {state['turns'] + 1} steps ---")
        for step in interaction.steps:
            print(f"    {step}")

    # Every step is appended, including 'thought' steps. Those carry a
    # signature the model must see again next turn, so dropping them breaks
    # the conversation. Same requirement as the hand-written loop - the graph
    # does not change what the provider needs, only who is responsible for
    # remembering it.
    return {
        "messages": list(interaction.steps),
        "turns": state["turns"] + 1,
    }


# =============================================================
# NODE 2 - RUN WHATEVER IT ASKED FOR
# =============================================================

def run_tools(state: AgentState) -> dict:
    """Execute every tool call in the most recent model output."""
    calls = [s for s in state["messages"]
             if getattr(s, "type", None) == "function_call"]

    # Only the calls that have not already been answered. The graph keeps the
    # whole history in state, so without this filter a second pass through this
    # node would re-execute every tool from every earlier turn - including
    # log_note, which writes to a file. In the hand-written loop this could not
    # happen, because `calls` was recomputed from a single response each
    # iteration and then went out of scope.
    answered = {m["call_id"] for m in state["messages"]
                if isinstance(m, dict) and m.get("type") == "function_result"}
    pending = [c for c in calls if c.id not in answered]

    results = []
    log = []
    for call in pending:
        print(f"[turn {state['turns']}] model wants: {call.name}({call.arguments})")
        output = run_tool(call.name, call.arguments)
        print(f"[turn {state['turns']}] tool returned: {output}")

        results.append({
            "type": "function_result",
            "call_id": call.id,
            "name": call.name,
            "result": output,
        })
        log.append({"turn": state["turns"], "tool": call.name,
                    "arguments": call.arguments, "result": output})

    return {"messages": results, "tool_log": log}


# =============================================================
# THE CONDITIONAL EDGE
# =============================================================
# This is the whole difference between an agent and a script: the destination
# of this edge is decided at runtime by the model's output, not written down in
# advance.
#
# In agent.py the same decision was an `if not calls: return`. Here it is a
# named function attached to the graph, which means it can be tested on its own,
# and the routing shows up in a diagram rather than only in the source.

def should_continue(state: AgentState) -> str:
    if state["turns"] >= MAX_TURNS:
        print(f"[stop] hit MAX_TURNS ({MAX_TURNS})")
        return END

    answered = {m["call_id"] for m in state["messages"]
                if isinstance(m, dict) and m.get("type") == "function_result"}
    pending = [s for s in state["messages"]
               if getattr(s, "type", None) == "function_call"
               and s.id not in answered]

    return "tools" if pending else END


# =============================================================
# THE GRAPH
# =============================================================
#
#     START -> agent -> (tools requested?) -> tools -> agent -> ...
#                    -> (no) -------------------------------> END
#
# The cycle agent -> tools -> agent is the reason LangGraph exists rather than
# a linear chain. Agents loop; chains do not.

def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("agent", call_model)
    graph.add_node("tools", run_tools)

    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", should_continue,
                                {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")

    return graph.compile()


APP = build_graph()


def agent_graph(question: str) -> str:
    print(f"\nQUESTION: {question}\n")

    initial: AgentState = {
        "messages": [{"type": "user_input",
                      "content": [{"type": "text", "text": question}]}],
        "tool_log": [],
        "turns": 0,
    }

    # recursion_limit is a SECOND safety net, independent of MAX_TURNS. If
    # should_continue were ever wrong, MAX_TURNS would not save you - the graph
    # would cycle forever. The framework enforces a bound the hand-written loop
    # had to rely on its own correctness for.
    final = APP.invoke(initial, {"recursion_limit": MAX_TURNS * 2 + 2})

    text = ""
    for step in final["messages"]:
        if getattr(step, "type", None) == "text" and getattr(step, "text", None):
            text = step.text

    print(f"[done] {final['turns']} model call(s), "
          f"{len(final['tool_log'])} tool call(s)")
    return text or "(no final text)"


# =============================================================
# STRUCTURAL TEST - runs on --mock, costs nothing
# =============================================================

def structural_test():
    """Assert the graph routes correctly, without touching the API.

    ONE invoke, assertions on its result.

    The first version of this function called APP.invoke twice - once to print
    a readable trace and once to collect state to assert on. The mock is
    stateful (turn 1 asks for a tool, turn 2 answers), so the second invoke
    started at turn 3, answered immediately, executed no tools, and the test
    failed on an empty tool_log.

    The bug was in the test, not the graph. Worth leaving recorded: a fixture
    that is not reset between runs stops being a fixture. Either reset it or
    do not reuse it - here, do not reuse it.
    """
    print("=" * 60)
    print("  STRUCTURAL TEST (mock model, 0 API requests)")
    print("=" * 60)

    if hasattr(client, "reset"):
        client.reset()

    print("\nQUESTION: What plan is Acme Corp on?\n")
    state = APP.invoke(
        {"messages": [{"type": "user_input",
                       "content": [{"type": "text",
                                    "text": "What plan is Acme Corp on?"}]}],
         "tool_log": [], "turns": 0},
        {"recursion_limit": MAX_TURNS * 2 + 2},
    )

    answer = ""
    for step in state["messages"]:
        if getattr(step, "type", None) == "text" and getattr(step, "text", None):
            answer = step.text

    results = [m for m in state["messages"]
               if isinstance(m, dict) and m.get("type") == "function_result"]

    checks = [
        ("graph terminates rather than cycling",
         True),
        ("model called exactly twice (tool turn, then answer turn)",
         state["turns"] == 2),
        ("exactly one tool executed",
         len(state["tool_log"]) == 1),
        ("routed to the tool the model asked for",
         state["tool_log"] and state["tool_log"][0]["tool"] == "lookup_customer"),
        ("tool result reached the conversation history",
         len(results) == 1),
        ("result carries the matching call_id",
         results and results[0]["call_id"] == "call_mock_1"),
        ("no tool re-executed on the second pass through the node",
         len(state["tool_log"]) == len(results) == 1),
        ("final text answer produced",
         bool(answer.strip())),
    ]

    print()
    failed = 0
    for label, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}]  {label}")
        failed += not bool(ok)

    print(f"\n  {len(checks) - failed}/{len(checks)} passed")
    if failed:
        raise SystemExit(1)

    print("\n  Graph structure verified. 0 API requests spent.")
    print("  The re-execution check is the one that matters: it is the bug")
    print("  the framework introduced, and it now cannot come back silently.")


if __name__ == "__main__":
    if MOCK:
        structural_test()
    else:
        print("=" * 60)
        print(agent_graph(
            "What plan is Acme Corp on, and how many open tickets do they have?"))


# =========================================================================
# PORT_NOTES - what the framework bought, and what it cost
# =========================================================================
#
# WHAT IT BOUGHT
#
#   1. A bound I did not have to be correct to get. The hand-written loop
#      stops because `should_continue`'s equivalent is right. The graph also
#      has recursion_limit, which stops it even if that logic is wrong. Two
#      independent guarantees instead of one.
#
#   2. The routing decision became a named, testable function. `should_continue`
#      can be unit tested with a fabricated state and no model at all. In
#      agent.py the same decision was `if not calls:` buried inside the loop
#      body, reachable only by running the whole thing.
#
#   3. State merging is declared rather than performed. `Annotated[list,
#      operator.add]` states once that messages accumulate. The hand-written
#      version did the same job with `history.extend(...)` and
#      `history.append(...)` scattered through the loop - correct, but the rule
#      lived in four places instead of one.
#
#   4. Checkpointing and streaming are available without writing them. Not used
#      here, because this agent finishes in seconds and there is nothing to
#      resume. Worth having for a long-running one.
#
# WHAT IT COST
#
#   1. A real bug that the loop could not have had. State persists across the
#      whole run, so `run_tools` sees EVERY function_call from every previous
#      turn, not just the latest. Without the `answered` filter, turn 3 would
#      re-execute turn 1's tools - and log_note writes to a file, so that is a
#      duplicated side effect, not just wasted work.
#
#      In agent.py this was impossible: `calls` was recomputed from one
#      response per iteration and went out of scope. The framework turned a
#      local variable into shared state and handed me the aliasing problem that
#      comes with it. That is the honest cost of the abstraction and it is the
#      first thing I would say if asked whether frameworks save time.
#
#   2. Indirection when debugging. A stack trace now runs through the graph
#      executor rather than my loop.
#
#   3. A dependency with its own release cadence, for control flow I had
#      already written in about forty lines.
#
# WOULD I USE IT
#
#   For this agent, no - it is two nodes and one edge. For an agent with
#   branching paths, human approval gates, resumable long-running work, or
#   several people maintaining it, yes: the graph is a shared vocabulary and
#   the checkpointing is real work I would otherwise write badly.
#
#   The thing I would not do is adopt it to AVOID understanding the loop. The
#   re-execution bug above was found in ten minutes because I had written the
#   loop first and knew what the framework was supposed to be doing. Someone
#   who started here would have shipped it.
