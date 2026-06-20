from carbon_agent.agent import build_schedule_graph


def test_schedule_graph_compiles_with_expected_nodes():
    g = build_schedule_graph()
    nodes = set(g.get_graph().nodes)
    assert {"propose", "commit"}.issubset(nodes)
