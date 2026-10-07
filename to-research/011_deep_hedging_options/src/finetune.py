"""finetune.py - Fine-tuning script for VolatilityTransformer.

Reference implementation.
"""
import torch
from config import MODEL_WEIGHTS_PATH
from transformer import VolatilityTransformer


def finetune(train_loader, val_loader, epochs: int = 10, lr: float = 1e-4):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = VolatilityTransformer().to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)

    for epoch in range(epochs):
        model.train()
        train_loss = 0.0
        for x, y in train_loader:
            x, y = x.to(device), y.to(device)
            optimizer.zero_grad()
            pred = model(x)
            loss = torch.nn.functional.mse_loss(pred, y)
            loss.backward()
            optimizer.step()
            train_loss += loss.item()

        val_loss = 0.0
        model.eval()
        with torch.no_grad():
            for x, y in val_loader:
                x, y = x.to(device), y.to(device)
                pred = model(x)
                val_loss += torch.nn.functional.mse_loss(pred, y).item()
        val_loss /= len(val_loader.dataset)

        print(f"Epoch {epoch}/{epochs} | Train Loss: {train_loss:.4f} | Val Loss: {val_loss:.4f}")

    torch.save(model.state_dict(), MODEL_WEIGHTS_PATH)
    print(f"Weights successfully saved to: {MODEL_WEIGHTS_PATH}")
