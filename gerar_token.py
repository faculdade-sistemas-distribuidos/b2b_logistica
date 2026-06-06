#!/usr/bin/env python3
"""
gerar_token.py — Utilitário para geração de tokens JWT válidos.

Uso:
  python gerar_token.py browser      → URL pronta para abrir o Frontend no navegador
  python gerar_token.py demandas     → Instrução de cabeçalho HTTP para integração server-to-server

O script lê as variáveis JWT_* diretamente do arquivo .env na raiz do projeto.
O algoritmo e o payload são gerados exatamente conforme o contrato do portal-autenticacao
(PR #1 — rrosantos), garantindo que o token seja aceito pela API do logistica-service.
"""

import argparse
import datetime
import hmac
import hashlib
import base64
import json
import os
import sys
from pathlib import Path


# ────────────────────────────────────────────────────────────────────────────
# Carregar .env manualmente (sem dependência de python-dotenv no PATH global)
# ────────────────────────────────────────────────────────────────────────────

def _load_env(env_path: Path) -> dict[str, str]:
    """Lê pares KEY=VALUE do arquivo .env, ignorando comentários e linhas vazias."""
    env_vars: dict[str, str] = {}
    if not env_path.exists():
        return env_vars
    with env_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            # Remove aspas opcionais ao redor do valor
            value = value.strip().strip('"').strip("'")
            env_vars[key.strip()] = value
    return env_vars


def load_config() -> dict[str, str]:
    """
    Carrega configuração JWT do .env (raiz do projeto).
    Fallback: variáveis de ambiente do sistema operacional.
    """
    project_root = Path(__file__).resolve().parent
    env_path = project_root / ".env"
    env_vars = _load_env(env_path)

    def get(key: str, default: str = "") -> str:
        return env_vars.get(key) or os.environ.get(key, default)

    return {
        "secret":              get("JWT_SECRET"),
        "issuer":              get("JWT_ISSUER",              "portal-autenticacao"),
        "audience":            get("JWT_AUDIENCE",            "portal-b2b"),
        "expiration_minutes":  get("JWT_EXPIRATION_MINUTES",  "240"),
    }


# ────────────────────────────────────────────────────────────────────────────
# Implementação HMAC-SHA256 pura (sem dependência de PyJWT)
# ────────────────────────────────────────────────────────────────────────────

def _b64url_encode(data: bytes) -> str:
    """Codifica bytes em Base64URL sem padding (RFC 7515)."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    """Decodifica Base64URL sem padding."""
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.urlsafe_b64decode(s)


def gerar_jwt(secret: str, payload: dict) -> str:
    """
    Gera um token JWT assinado com HMAC-SHA256.

    Compatível com o padrão RFC 7519. Não requer bibliotecas externas além
    da biblioteca padrão do Python.
    """
    header = {"alg": "HS256", "typ": "JWT"}
    header_b64  = _b64url_encode(json.dumps(header,  separators=(",", ":")).encode())
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode())

    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    signature = hmac.new(
        secret.encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).digest()

    return f"{header_b64}.{payload_b64}.{_b64url_encode(signature)}"


# ────────────────────────────────────────────────────────────────────────────
# Construção do payload conforme contrato do portal-autenticacao
# ────────────────────────────────────────────────────────────────────────────

def build_payload(subject: str, nome: str, config: dict) -> dict:
    """
    Monta o payload JWT com os claims exigidos pelo logistica-service:
      - sub  : identificador único do cliente/sistema
      - name : nome legível (para logs e auditoria)
      - iss  : emissor (deve ser 'portal-autenticacao')
      - aud  : audiência (deve ser 'portal-b2b')
      - iat  : timestamp de emissão
      - exp  : timestamp de expiração
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    exp_minutes = int(config["expiration_minutes"])

    return {
        "sub":  subject,
        "name": nome,
        "iss":  config["issuer"],
        "aud":  config["audience"],
        "iat":  int(now.timestamp()),
        "exp":  int((now + datetime.timedelta(minutes=exp_minutes)).timestamp()),
    }


# ────────────────────────────────────────────────────────────────────────────
# Subjects pré-definidos
# ────────────────────────────────────────────────────────────────────────────

SUBJECTS = {
    "browser":  ("usuario-logistica-dev",  "Operador Logística (acesso via browser)"),
    "demandas": ("svc-demandas",           "Sistema Demandas (integração server-to-server)"),
}


# ────────────────────────────────────────────────────────────────────────────
# Saída formatada por destinatário
# ────────────────────────────────────────────────────────────────────────────

FRONTEND_URL = "http://34.8.17.245/logistica/"

ANSI_GREEN  = "\033[92m"
ANSI_CYAN   = "\033[96m"
ANSI_YELLOW = "\033[93m"
ANSI_RESET  = "\033[0m"
ANSI_BOLD   = "\033[1m"


def imprimir_browser(token: str) -> None:
    url = f"{FRONTEND_URL}?jwt={token}"
    print()
    print(f"{ANSI_BOLD}{ANSI_GREEN}✅ Token gerado para acesso via navegador{ANSI_RESET}")
    print(f"{ANSI_CYAN}{'─' * 72}{ANSI_RESET}")
    print(f"{ANSI_BOLD}URL pronta para colar no navegador:{ANSI_RESET}")
    print()
    print(f"  {url}")
    print()
    print(f"{ANSI_CYAN}{'─' * 72}{ANSI_RESET}")
    print(f"{ANSI_YELLOW}⚠  O token expira em {ANSI_RESET}", end="")


def imprimir_demandas(token: str) -> None:
    print()
    print(f"{ANSI_BOLD}{ANSI_GREEN}✅ Token gerado para integração server-to-server (Demandas){ANSI_RESET}")
    print(f"{ANSI_CYAN}{'─' * 72}{ANSI_RESET}")
    print(f"{ANSI_BOLD}Cabeçalho HTTP a incluir em todas as requisições:{ANSI_RESET}")
    print()
    print(f"  Authorization: Bearer {token}")
    print()
    print(f"{ANSI_CYAN}{'─' * 72}{ANSI_RESET}")
    print(f"{ANSI_YELLOW}⚠  O token expira em ", end="")


def imprimir_expiracao(config: dict) -> None:
    minutes = int(config["expiration_minutes"])
    hours   = minutes // 60
    mins    = minutes % 60
    duracao = f"{hours}h{mins:02d}min" if hours else f"{mins}min"
    print(f"{duracao}.{ANSI_RESET}")
    print()


# ────────────────────────────────────────────────────────────────────────────
# Entrypoint
# ────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="gerar_token.py",
        description=(
            "Gera tokens JWT válidos para o Portal B2B Logística.\n\n"
            "  browser   → URL pronta para abrir o Frontend no navegador\n"
            "  demandas  → Cabeçalho Authorization: Bearer para integração REST"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "destinatario",
        choices=list(SUBJECTS.keys()),
        help="Destinatário do token: 'browser' (acesso humano) ou 'demandas' (sistema externo)",
    )
    parser.add_argument(
        "--expiracao",
        metavar="MINUTOS",
        type=int,
        default=None,
        help="Sobrescreve o tempo de expiração em minutos (padrão: JWT_EXPIRATION_MINUTES do .env)",
    )

    args = parser.parse_args()

    # Carregar configuração
    config = load_config()

    if not config["secret"]:
        print(
            f"\n{ANSI_YELLOW}❌ ERRO: JWT_SECRET não encontrado.\n"
            f"   Adicione JWT_SECRET ao arquivo .env na raiz do projeto.\n"
            f"   Consulte .env.example para referência.{ANSI_RESET}\n",
            file=sys.stderr,
        )
        sys.exit(1)

    # Aplicar override de expiração via argumento CLI
    if args.expiracao is not None:
        config["expiration_minutes"] = str(args.expiracao)

    # Montar payload e gerar token
    subject, nome = SUBJECTS[args.destinatario]
    payload = build_payload(subject, nome, config)
    token   = gerar_jwt(config["secret"], payload)

    # Exibir resultado
    if args.destinatario == "browser":
        imprimir_browser(token)
    else:
        imprimir_demandas(token)

    imprimir_expiracao(config)


if __name__ == "__main__":
    main()
