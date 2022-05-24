FROM python:3.9.5-slim

ENV PYTHONUNBUFFERED=0
ENV POETRY_VERSION=1.1.11
#
# Install packages needed by the buildchain
#
RUN apt-get upgrade
RUN apt-get --assume-yes update \
 && DEBIAN_FRONTEND=noninteractive apt-get install --no-install-recommends --assume-yes \
    curl \
    git

RUN pip install "poetry==$POETRY_VERSION"

WORKDIR /app

COPY poetry.lock pyproject.toml /app/

RUN poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi --no-dev --no-root

COPY . /app/

CMD ["uvicorn", "srcs.web.app:app", "--host", "0.0.0.0", "--port", "80"]
