"""Optional weak supervision from the canonical rule engine, never ground truth."""
import argparse
import json
from pathlib import Path
from backend.services.risk_analyzer import rule_matches


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    rows=[]
    for line in Path(args.input).read_text().splitlines():
        if line.strip():
            row=json.loads(line)
            matches=rule_matches(row['text'])
            rows.append({**row,'label':matches[0].category if matches else 'no_risk','annotation_method':'weak_label','ground_truth_eligible':False})
    Path(args.output).write_text(''.join(json.dumps(row)+'\n' for row in rows))


if __name__=='__main__':
    main()
