import pytest
import sys
import argparse
from unittest.mock import patch, MagicMock

from scdm.__main__ import main, cli_approval_callback
from scdm.domain.state import WorkflowState
from scdm.domain.schemas import Recommendation
from scdm.domain.constants import ApprovalState, DataLayer

def test_cli_mock_mode_executes_successfully():
    with patch("sys.argv", ["scdm", "--focal-company", "test", "--query", "shortage", "--mode", "MOCK"]):
        with patch("builtins.input", return_value="y"):
            # Should not raise exception
            main()

def test_cli_approval_callback_approved():
    wf = WorkflowState()
    rec = Recommendation(
        recommendation_id="r1", action="TEST", target_supplier_id="sup1",
        risk_context="HIGH", reasons=[], evidence_references=[],
        uncertainty="None", layer=DataLayer.RECOMMENDATION
    )
    wf.recommendations.append(rec)
    
    with patch("builtins.input", return_value="y"):
        cli_approval_callback(wf)
        
    assert wf.pending_approvals["r1"] == ApprovalState.APPROVED

def test_cli_approval_callback_rejected():
    wf = WorkflowState()
    rec = Recommendation(
        recommendation_id="r1", action="TEST", target_supplier_id="sup1",
        risk_context="HIGH", reasons=[], evidence_references=[],
        uncertainty="None", layer=DataLayer.RECOMMENDATION
    )
    wf.recommendations.append(rec)
    
    with patch("builtins.input", return_value="n"):
        cli_approval_callback(wf)
        
    assert wf.pending_approvals["r1"] == ApprovalState.REJECTED

def test_cli_invalid_mode():
    with patch("sys.argv", ["scdm", "--focal-company", "test", "--query", "shortage", "--mode", "INVALID"]):
        with pytest.raises(SystemExit):
            main()
