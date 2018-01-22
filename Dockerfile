FROM       centos:7
MAINTAINER sqre-admin
LABEL      description="Slack <-> GitHub user mapper" \
           name="lsstsqre/uservice-ghslacker"

USER       root
RUN        yum install -y epel-release
RUN        yum repolist
RUN        yum install -y git python-pip python-devel
RUN        yum install -y gcc openssl-devel
RUN        pip install --upgrade pip
RUN        useradd -d /home/uwsgi -m uwsgi
RUN        mkdir /dist

# Must run python setup.py sdist first.
ARG        VERSION="0.0.1"
LABEL      version="$VERSION"
COPY       dist/sqre-uservice-ghslacker-$VERSION.tar.gz /dist
RUN        pip install /dist/sqre-uservice-ghslacker-$VERSION.tar.gz

USER       uwsgi
WORKDIR    /home/uwsgi
COPY       uwsgi.ini .
EXPOSE     5000
CMD        [ "uwsgi", "-T", "uwsgi.ini" ]
