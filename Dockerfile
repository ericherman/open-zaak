# Stage 1 - Compile needed python dependencies
FROM python:3.7-stretch AS build

RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY ./requirements /app/requirements
RUN pip install pip setuptools -U
RUN pip install -r requirements/production.txt


# Stage 2 - build frontend
FROM mhart/alpine-node:10 AS frontend-build

WORKDIR /app

COPY ./*.json /app/
RUN npm ci

COPY ./Gulpfile.js /app/
COPY ./build /app/build/

COPY src/openzaak/sass/ /app/src/openzaak/sass/
RUN npm run build


# Stage 3 - Build docker image suitable for execution and deployment
FROM python:3.7-stretch AS production

# Stage 3.1 - Set up the needed production dependencies
# install all the dependencies for GeoDjango
RUN apt-get update && apt-get install -y --no-install-recommends \
        postgresql-client \
        libgdal20 \
        libgeos-c1v5 \
        libproj12 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=build /usr/local/lib/python3.7 /usr/local/lib/python3.7
COPY --from=build /usr/local/bin/uwsgi /usr/local/bin/uwsgi

# Stage 3.2 - Copy source code
WORKDIR /app
COPY ./bin/docker_start.sh /start.sh
RUN mkdir /app/log

COPY --from=frontend-build /app/src/openzaak/static/css /app/src/openzaak/static/css
COPY ./src /app/src
COPY ./fixtures /app/fixtures
ARG COMMIT_HASH
ENV GIT_SHA=${COMMIT_HASH}

ENV DJANGO_SETTINGS_MODULE=openzaak.conf.docker

ARG SECRET_KEY=dummy

# Run collectstatic, so the result is already included in the image
RUN python src/manage.py collectstatic --noinput

EXPOSE 8000
CMD ["/start.sh"]
