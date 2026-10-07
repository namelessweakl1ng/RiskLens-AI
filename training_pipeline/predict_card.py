import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification


MODEL_PATH = "training_pipeline/models/card_finbert"


# Load trained model
tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
model = AutoModelForSequenceClassification.from_pretrained(MODEL_PATH)

model.eval()


def predict_clause(text):
    inputs = tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        max_length=512
    )

    with torch.no_grad():
        outputs = model(**inputs)

    probabilities = torch.softmax(outputs.logits, dim=1)

    predicted_id = torch.argmax(probabilities, dim=1).item()

    confidence = probabilities[0][predicted_id].item() * 100

    label = model.config.id2label[predicted_id]

    return label, confidence


if __name__ == "__main__":

    print("=" * 60)
    print("FINTEL - CREDIT CARD RISK CLAUSE ANALYZER")
    print("=" * 60)

    while True:

        text = input("\nEnter a card clause (or type 'exit'): ")

        if text.lower() == "exit":
            break

        label, confidence = predict_clause(text)

        print("\nPrediction :", label)
        print(f"Confidence : {confidence:.2f}%")