import os
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, avg, udf
from pyspark.sql.types import DoubleType
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import SGDRegressor
import numpy as np
import pyarrow as pa

spark = SparkSession.builder \
    .appName("Spark Homework") \
    .master("yarn") \
    .config("spark.executor.instances", "2") \
    .getOrCreate()

ratings = spark.read.option("header", "true").csv("hdfs://192.168.34.2:8020/ml-latest-small/ratings.csv")
tags = spark.read.option("header", "true").csv("hdfs://192.168.34.2:8020/ml-latest-small/tags.csv")

ratings_count = ratings.count()
tags_count = tags.count()

unique_movies = ratings.select("movieId").distinct().count()
unique_users = ratings.select("userId").distinct().count()

good_ratings = ratings.filter(col("rating") >= 4.0).count()

ratings_time = ratings.select("userId", "movieId", col("timestamp").alias("rating_time"))
tags_time = tags.select("userId", "movieId", col("timestamp").alias("tag_time"))
joined = ratings_time.join(tags_time, ["userId", "movieId"])
time_diff = joined.withColumn("diff", (col("tag_time") - col("rating_time")).cast(DoubleType()))
avg_time_diff = time_diff.select(avg("diff")).first()[0]

user_avg = ratings.groupBy("userId").agg(avg("rating").alias("user_avg"))
avg_of_avgs = user_avg.agg(avg("user_avg")).first()[0]

tags_ratings = tags.join(ratings, ["userId", "movieId"])
pandas_df = tags_ratings.select("tag", "rating").dropna().toPandas()
vectorizer = TfidfVectorizer()
X = vectorizer.fit_transform(pandas_df["tag"].astype(str))
y = pandas_df["rating"].astype(float)
reg = SGDRegressor(max_iter=1000, tol=1e-3)
reg.fit(X, y)

def predict_rating(tag):
    X_tag = vectorizer.transform([str(tag)])
    return float(reg.predict(X_tag)[0])

predict_udf = udf(predict_rating, DoubleType())
tags_ratings = tags_ratings.withColumn("predicted_rating", predict_udf(col("tag")))
tags_ratings_pd = tags_ratings.select("predicted_rating", "rating").dropna().toPandas()
rmse = np.sqrt(np.mean((tags_ratings_pd["predicted_rating"] - tags_ratings_pd["rating"]) ** 2))

results = [
    f"stages:0 tasks:0",  # TODO: Реализовать подсчёт stages/tasks через SparkListener при необходимости
    f"filmsUnique:{unique_movies} usersUnique:{unique_users}",
    f"goodRating:{good_ratings}",
    f"timeDifference:{avg_time_diff}",
    f"avgRating:{avg_of_avgs}",
    f"rmse:{rmse}"
]

fs = pa.hdfs.connect('192.168.34.2', 8020, user='hadoop')
with fs.open('/sparkExperiments.txt', 'wb') as f:
    for line in results:
        f.write((line + '\n').encode())

spark.stop()