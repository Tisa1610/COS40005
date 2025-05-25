import pandas as pd
import numpy as np
import os

def generate_data(seed, filename):
    np.random.seed(seed)
    X = np.random.rand(100, 3) * 100  
    y = (X[:, 0] > 70) | (X[:, 1] > 50)  
    df = pd.DataFrame(X, columns=["cpu", "file_rate", "ext_flag"])
    df["label"] = y.astype(int)
    df.to_csv(filename, index=False)

os.makedirs("data", exist_ok=True)
generate_data(1, "data/client1.csv")
generate_data(2, "data/client2.csv")
generate_data(3, "data/client3.csv")
generate_data(99, "data/test.csv")
