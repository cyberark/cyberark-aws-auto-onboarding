FROM python:3.6-alpine

RUN apk add --update-cache \
    zip

RUN python3 -m pip install virtualenv && \
    python3 -m virtualenv .testenv && \
    source ./.testenv/bin/activate

RUN pip install safety bandit

COPY run.sh /run.sh

CMD /run.sh