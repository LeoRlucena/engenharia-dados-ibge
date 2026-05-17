FROM jupyter/scipy-notebook

USER root
RUN mkdir -p /home/jovyan/work && \
    chown -R 1000:1000 /home/jovyan/work && \
    chmod -R 755 /home/jovyan/work

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

USER jovyan