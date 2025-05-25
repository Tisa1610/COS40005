import numpy as np

def aggregate_weights(weights_list, intercepts_list):
    avg_weights = np.mean(weights_list, axis=0)
    avg_intercepts = np.mean(intercepts_list, axis=0)
    return avg_weights, avg_intercepts
