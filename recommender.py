import sqlite3
import pandas as pd
from sklearn.preprocessing import OneHotEncoder
from sklearn.metrics.pairwise import cosine_similarity

def build_similarity_matrix(db_path):
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query("SELECT id, primary_muscle, equipment, type, difficulty FROM exercises", conn)
    encoder = OneHotEncoder()
    features = encoder.fit_transform(df[['primary_muscle', 'equipment', 'type', 'difficulty']]).toarray()
    sim_matrix = cosine_similarity(features)
    
    similar_exercises = {}
    for i, row in enumerate(sim_matrix):
        similar_indices = row.argsort()[::-1][1:6]
        similar_ids = df.iloc[similar_indices]['id'].tolist()
        similar_exercises[df.iloc[i]['id']] = similar_ids

    conn.close()
    return similar_exercises