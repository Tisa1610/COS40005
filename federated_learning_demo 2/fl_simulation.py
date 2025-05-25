from client_model import ClientModel
from server_aggregate import aggregate_weights
import multiprocessing as mp
import pandas as pd
import numpy as np
from sklearn.metrics import accuracy_score
import matplotlib.pyplot as plt

client_ids = [1, 2, 3]

def train_client(client_id, return_dict):
    model = ClientModel(client_id)
    weights, intercepts = model.train()
    return_dict[client_id] = (weights, intercepts)
    print(f"Client {client_id} finished training.")

if __name__ == "__main__":
    manager = mp.Manager()
    return_dict = manager.dict()
    processes = []

    for cid in client_ids:
        p = mp.Process(target=train_client, args=(cid, return_dict))
        processes.append(p)
        p.start()

    for p in processes:
        p.join()

    weights = [return_dict[cid][0] for cid in client_ids]
    intercepts = [return_dict[cid][1] for cid in client_ids]
    avg_weights, avg_intercepts = aggregate_weights(weights, intercepts)

    
    test_df = pd.read_csv("data/test.csv")
    X_test = test_df.drop("label", axis=1)
    y_test = test_df["label"]
    preds = (np.dot(X_test, avg_weights.T) + avg_intercepts > 0).astype(int).flatten()
    acc = accuracy_score(y_test, preds)

    
    plt.plot(y_test[:30].values, label="Actual", marker='o')
    plt.plot(preds[:30], label="FL Prediction", marker='x')
    plt.title(f"FL Accuracy: {acc:.2f}")
    plt.xlabel("Sample Index")
    plt.ylabel("Class")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("federated_learning_results.png")
    print(f"Demo complete. Accuracy: {acc:.2f}. Graph saved as 'federated_learning_results.png'")
