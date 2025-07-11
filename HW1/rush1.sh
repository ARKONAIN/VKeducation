#!/bin/bash
set -e

wait_for_hadoop_service() {
    local service_host=$1
    local service_port=$2
    until nc -z "$service_host" "$service_port"; do
        echo "Ожидание доступности сервиса Hadoop на $service_host:$service_port..."
        sleep 3
    done
}

execute_hadoop_tasks() {
    wait_for_hadoop_service 192.168.34.2 8020
    wait_for_hadoop_service 192.168.34.2 8032

    echo "Создание тестовой директории /createme в HDFS..."
    hdfs dfs -mkdir -p /createme

    echo "Очистка временной директории /delme..."
    hdfs dfs -rm -r -f /delme || true
    echo "Содержимое корневой директории HDFS:"
    hdfs dfs -ls / | awk '{print $8}' || true
    echo "------------------------------------"

    echo "Создание тестового файла /nonnull.txt..."
    echo "sample-content-123" | hdfs dfs -put -f - /nonnull.txt

    echo "Подготовка к запуску MapReduce задачи..."
    hdfs dfs -rm -r -f /output >/dev/null 2>&1 || true
    
    echo "Запуск задачи wordcount для файла /shadow.txt..."
    hadoop jar "$HADOOP_HOME"/share/hadoop/mapreduce/hadoop-mapreduce-examples-*.jar \
        wordcount /shadow.txt /output 2>/dev/null

    echo "Анализ результатов выполнения задачи..."
    words_count_result=$(hdfs dfs -cat /output/part-r-00000 2>/dev/null | 
           awk '$1 == "Innsmouth" {sum += $2} END{print sum+0}')
    
    echo "Обнаружено вхождений слова 'Innsmouth': $words_count_result"
    echo "Сохранение результата в /whataboutinsmouth.txt..."
    echo "$words_count_result" | hdfs dfs -put -f - /whataboutinsmouth.txt
}

execute_hadoop_tasks "$@"