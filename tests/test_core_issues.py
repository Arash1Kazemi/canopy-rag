"""Test area: Phase 7 Issue and Sub-Issue Modeling."""
from pathlib import Path
import pytest

from rag_core.issues.model import Issue, IssueIdentifier, IssueManager
from rag_core.issues.repository import CsvIssueRepository
from rag_core.organization.model import NodeIdentifier
from rag_core.shared.kernel import DomainError


def test_valid_issue_identifier():
    assert str(IssueIdentifier("I01")) == "I01"
    with pytest.raises(DomainError, match="issue id"):
        IssueIdentifier("X01")


def test_issue_validation():
    node_id = NodeIdentifier("N6")
    i_id = IssueIdentifier("I01")
    
    # Valid issue
    issue = Issue(issue_id=i_id, node_id=node_id, title="Route 7 overcrowded", description="Peak load above limit", status="analyzing")
    assert issue.title == "Route 7 overcrowded"

    # Empty title
    with pytest.raises(DomainError, match="title"):
        Issue(issue_id=i_id, node_id=node_id, title="   ", description="desc", status="new")

    # Invalid status
    with pytest.raises(DomainError, match="status"):
        Issue(issue_id=i_id, node_id=node_id, title="title", description="desc", status="invalid_status")


def test_issue_manager_and_sub_issues():
    manager = IssueManager()
    n = NodeIdentifier("N6")
    
    parent = Issue(IssueIdentifier("I01"), n, "Parent Issue", "Main problem description", "analyzing")
    child = Issue(IssueIdentifier("I02"), n, "Sub Issue", "Sub problem description", "new", parent_issue_id=IssueIdentifier("I01"))
    
    manager.add_issue(parent)
    manager.add_issue(child)
    
    assert len(manager.all_issues()) == 2
    assert len(manager.sub_issues(IssueIdentifier("I01"))) == 1
    assert manager.sub_issues(IssueIdentifier("I01"))[0].issue_id.value == "I02"


def test_load_case_study_issues():
    repo = CsvIssueRepository(Path("case_study/issues.csv"))
    manager = repo.load()
    issues = manager.all_issues()
    assert len(issues) >= 7  # 7 issues in case_study/issues.csv
    
    # Check specific issue I01
    i01 = manager.get_issue(IssueIdentifier("I01"))
    assert i01 is not None
    assert i01.node_id.value == "N6"
    assert i01.status == "analyzing"
    
    # Check sub-issues of I01
    subs = manager.sub_issues(IssueIdentifier("I01"))
    sub_ids = {str(s.issue_id) for s in subs}
    assert {"I02", "I03", "I04"}.issubset(sub_ids)


def test_issue_comparison():
    manager = IssueManager()
    n = NodeIdentifier("N6")
    
    i1 = Issue(IssueIdentifier("I01"), n, "Route 7 overcrowded", "Peak load above the 85% policy limit on Route 7", "analyzing")
    i2 = Issue(IssueIdentifier("I02"), n, "Route 7 crowding issue", "Peak passenger load above limit on Route 7", "new")
    i3 = Issue(IssueIdentifier("I03"), n, "Water quality standard", "Nitrate level above threshold", "unsolved")
    
    manager.add_issue(i1)
    manager.add_issue(i2)
    manager.add_issue(i3)
    
    sim_1_2 = manager.compare_issues(IssueIdentifier("I01"), IssueIdentifier("I02"))
    sim_1_3 = manager.compare_issues(IssueIdentifier("I01"), IssueIdentifier("I03"))
    
    assert sim_1_2 > sim_1_3
    assert 0.0 <= sim_1_3 <= 1.0
