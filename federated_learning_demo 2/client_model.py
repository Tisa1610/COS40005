import pandas as pd
from sklearn.linear_model import LogisticRegression

class ClientModel:
    def __init__(self, client_id):
        self.client_id = client_id
        self.model = LogisticRegression()
        self.path = f"data/client{client_id}.csv"

    def train(self):
        df = pd.read_csv(self.path)
        X = df.drop("label", axis=1)
        y = df["label"]
        self.model.fit(X, y)
        return self.model.coef_, self.model.intercept_
