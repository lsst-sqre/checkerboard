FROM       python:3.7

MAINTAINER sqre-admin
LABEL      description="Slack <-> GitHub user mapper" \
           name="lsstsqre/checkerboard"

ARG        VERSION="0.2.0"
LABEL      version="$VERSION"

# Must run python setup.py sdist first.
RUN        mkdir /dist
COPY       dist/checkerboard-$VERSION.tar.gz /dist
RUN        pip install /dist/checkerboard-$VERSION.tar.gz \
           && rm /dist/checkerboard-$VERSION.tar.gz

USER       root
RUN        useradd -d /home/uwsgi -m uwsgi

USER       uwsgi
WORKDIR    /home/uwsgi
COPY       uwsgi.ini .
EXPOSE     5000
CMD        [ "uwsgi", "-T", "uwsgi.ini" ]
