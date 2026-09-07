from claimlens.policy.retrieve import PolicyRetriever, retrieve_policy_guidance


def test_retrieve_total_loss_clause():
    res = retrieve_policy_guidance("what is the total loss 50% economic write-off threshold?")
    assert res.is_established
    assert res.matched_clause is not None
    assert res.matched_clause.id == "clause_01_total_loss_economic"
    assert "Clause 4.1" in res.citation
    assert res.relevance_score > 0.20


def test_retrieve_chassis_structural_clause():
    res = retrieve_policy_guidance(
        "is deformation to vehicle chassis frame and quarter-panel unibody covered?"
    )
    assert res.is_established
    assert res.matched_clause is not None
    assert res.matched_clause.id == "clause_02_chassis_structural"
    assert "Clause 4.2" in res.citation
    assert "chassis" in res.text.lower()


def test_retrieve_glass_windshield_clause():
    res = retrieve_policy_guidance(
        "is shattered windshield glass and ADAS camera sensor calibration covered?"
    )
    assert res.is_established
    assert res.matched_clause is not None
    assert res.matched_clause.id == "clause_03_glass_windshield"
    assert "Clause G-1" in res.citation
    assert "windshield" in res.text.lower()


def test_retrieve_agency_repair_clause():
    res = retrieve_policy_guidance("can I repair at the main dealership agency workshop?")
    assert res.is_established
    assert res.matched_clause is not None
    assert res.matched_clause.id == "clause_05_repair_agency_choice"
    assert "Clause 3.1" in res.citation


def test_retrieve_irrelevant_query_returns_not_established():
    # An entirely unrelated topic should NOT hallucinate a match
    res = retrieve_policy_guidance("quantum mechanical teleportation of radioactive isotopes")
    assert not res.is_established
    assert res.matched_clause is None
    assert res.citation == "Not Established"
    assert "Clause Not Established" in res.title
    assert "abstains from citing speculative legal text" in res.guidance


def test_retrieve_empty_query_returns_not_established():
    res = retrieve_policy_guidance("   ... ???   ")
    assert not res.is_established
    assert res.citation == "Not Established"


def test_custom_clauses_dir(tmp_path):
    # Verify PolicyRetriever works with arbitrary clause folders
    custom_retriever = PolicyRetriever(clauses_dir=tmp_path)
    res = custom_retriever.search("test query")
    assert not res.is_established
