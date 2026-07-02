"""Graph enrichment for the visualization upgrade."""
from datetime import date

from app.api import dto


def test_graphnode_has_category_and_grounding_fields():
    n = dto.GraphNode(
        id="1", label="Allergic to penicillin", subject="allergy", value="penicillin",
        status="active", valid_from=date(2021, 8, 6), category="Allergy",
        source="Dr. Adams", confidence=1.0, ontology_valid=True,
    )
    assert n.category == "Allergy"
    assert n.ontology_valid is True


def test_graphedge_supports_family_and_risk_types():
    dto.GraphEdge(source="a", target="b", type="RELATED_TO", label="father")
    dto.GraphEdge(source="a", target="r", type="RISK", label="cardiovascular")


from app.api import routes_graph
from app.memory import ledger
from app.memory.schema import ClinicalFact


def test_graph_route_sets_category_from_resource_type(monkeypatch):
    f = ClinicalFact(patient_id="P0", subject="allergy", predicate="diagnosed",
                     value="penicillin", valid_from=date(2021, 8, 6),
                     resource_type="Allergy", source="Dr. Adams")
    f.ontology_valid = True
    monkeypatch.setattr(ledger, "all", lambda pid: [f])
    resp = routes_graph.graph(patient_id="P0")
    node = resp.nodes[0]
    assert node.category == "Allergy"
    assert node.ontology_valid is True


def test_graph_includes_family_relatives(monkeypatch):
    f = ClinicalFact(patient_id="P020", subject="diagnosis", predicate="diagnosed",
                     value="anemia", valid_from=date(2024, 1, 1), resource_type="Condition")
    monkeypatch.setattr(ledger, "all", lambda pid: [f] if pid == "P020" else [])
    import app.api.routes_graph as rg
    monkeypatch.setattr(rg, "_family_links", lambda pid: [
        {"patient_id": "P020", "relative_id": "P010", "relation": "father", "consent": True}])
    monkeypatch.setattr(rg, "_patient_name", lambda pid: "Rahul Sharma" if pid == "P010" else pid)
    resp = rg.graph(patient_id="P020")
    rel_nodes = [n for n in resp.nodes if n.kind == "relative"]
    rel_edges = [e for e in resp.edges if e.type == "RELATED_TO"]
    assert rel_nodes and rel_nodes[0].label.startswith("Father")
    assert rel_edges and rel_edges[0].label == "father"
