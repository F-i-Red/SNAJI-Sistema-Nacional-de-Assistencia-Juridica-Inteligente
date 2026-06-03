FROM python:3.12-slim

# Utilizador não-root
RUN groupadd -r snaji && useradd -r -g snaji snaji

WORKDIR /app

# Dependências do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código da aplicação
COPY app/ ./app/

# Permissões
RUN chown -R snaji:snaji /app
USER snaji

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
