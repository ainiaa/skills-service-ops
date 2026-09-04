#!/usr/bin/env python3
"""Judge saved external Agent routing results against the public trigger contract."""
import argparse
import json
from pathlib import Path


def values(value, field):
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    raise ValueError("{} 必须是字符串或字符串列表。".format(field))


def contract_cases(contract):
    cases = contract.get("cases") if isinstance(contract, dict) else None
    if not isinstance(cases, list):
        raise ValueError("评测契约必须包含 cases 列表。")
    seen = set()
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get("id"), str) or not case["id"]:
            raise ValueError("每个评测用例必须包含非空 id。")
        if case["id"] in seen:
            raise ValueError("评测契约包含重复 id：{}。".format(case["id"]))
        seen.add(case["id"])
    return cases


def behavior_reasons(case, result):
    reasons = []
    actual_route = values(result.get("actual_route"), "actual_route")
    if "expected_route" in case and actual_route != values(case["expected_route"], "expected_route"):
        reasons.append("route")
    actual_asked = set(values(result.get("actual_asked"), "actual_asked"))
    if not set(values(case.get("must_ask"), "must_ask")).issubset(actual_asked):
        reasons.append("ask")
    output = "\n".join(values(result.get("actual_output"), "actual_output"))
    observed = [*actual_route, *actual_asked]
    if any(any(value in item for item in observed) or value in output
           for value in values(case.get("must_not"), "must_not")):
        reasons.append("must_not")
    if not all(value in output for value in values(case.get("required_output"), "required_output")):
        reasons.append("output")
    return reasons


def evaluate(contract, results):
    expected = {case["id"]: case for case in contract_cases(contract)}
    observed = {}
    invalid_results = []
    for result in results:
        if not isinstance(result, dict):
            raise ValueError("每条评测结果必须是对象。")
        case_id = result.get("id")
        if case_id not in expected:
            invalid_results.append({"id": case_id, "reason": "unknown"})
        elif case_id in observed:
            invalid_results.append({"id": case_id, "reason": "duplicate"})
        else:
            observed[case_id] = result
    failed = []
    for case_id, case in expected.items():
        result = observed.get(case_id)
        reasons = []
        if result is None:
            reasons.append("missing")
        else:
            if "expected_action" in case and result.get("actual_action") != case["expected_action"]:
                reasons.append("action")
            if "expected_action" in case and result.get("actual_route") != case.get("expected_route"):
                reasons.append("route")
            if "expected_action" not in case:
                reasons.extend(behavior_reasons(case, result))
        if reasons:
            failed.append({"id": case_id, "reasons": reasons})
    return {"status": "passed" if not failed and not invalid_results else "failed", "failed": failed,
            "invalid_results": invalid_results, "passed": len(expected) - len(failed),
            "total": len(expected)}


def main():
    parser = argparse.ArgumentParser(description="校验外部 Agent 的 service-ops 触发评测结果")
    parser.add_argument("--cases", default=Path(__file__).parent.parent / "evals" / "triggers.json", type=Path)
    parser.add_argument("--results", required=True, type=Path,
                        help="JSONL：每行包含 id、actual_action、actual_route")
    args = parser.parse_args()
    try:
        contract = json.loads(args.cases.read_text(encoding="utf-8"))
        results = [json.loads(line) for line in args.results.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, ValueError) as error:
        parser.error("无法读取评测输入：{}".format(error))
    try:
        result = evaluate(contract, results)
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(result, ensure_ascii=False))
    if result["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
