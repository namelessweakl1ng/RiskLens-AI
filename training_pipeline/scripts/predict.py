import argparse
import json
from backend.services.fine_tuned_risk_model import RiskModel


def main():
    parser=argparse.ArgumentParser(description='Inspect genuine domain-classifier probabilities')
    parser.add_argument('--model',required=True)
    parser.add_argument('--text',required=True)
    args=parser.parse_args()
    model=RiskModel(args.model)
    if not model.status().model_loaded:
        parser.error(model.status().load_error)
    print(json.dumps(model.predict([args.text])[0],indent=2))


if __name__=='__main__':
    main()
