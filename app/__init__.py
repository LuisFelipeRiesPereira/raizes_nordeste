import os
from flask import Flask, jsonify, render_template_string
from app.infrastructure.database.base import Base, engine
from app.api.routes.auth_routes import auth_bp
from app.api.routes.pedidos_routes import pedidos_bp
from app.api.routes.outros_routes import (
    produtos_bp, unidades_bp, estoque_bp,
    pagamentos_bp, fidelidade_bp
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# -----------
# swagger ui servido direto pelo flask sem flasgger
# carrega o swagger.yaml e expoe no /docs/
# -----------

SWAGGER_UI_HTML = """
<!DOCTYPE html>
<html>
<head>
  <title>API Raizes do Nordeste</title>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
  <style>body{margin:0;padding:0;} .topbar{display:none!important;}</style>
</head>
<body>
<div id="swagger-ui"></div>
<script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
<script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-standalone-preset.js"></script>
<script>
window.onload = function() {
  SwaggerUIBundle({
    url: "/apispec.json",
    dom_id: '#swagger-ui',
    presets: [SwaggerUIBundle.presets.apis, SwaggerUIStandalonePreset],
    layout: "StandaloneLayout",
    deepLinking: true,
    tryItOutEnabled: true,
  })
}
</script>
</body>
</html>
"""


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "raizes-nordeste-secret-2026")

    @app.get("/docs/")
    @app.get("/docs")
    def swagger_ui():
        return render_template_string(SWAGGER_UI_HTML)

    @app.get("/apispec.json")
    def apispec():
        # le o yaml e serve como json pro swagger ui
        import yaml
        yaml_path = os.path.join(BASE_DIR, "docs", "swagger.yaml")
        with open(yaml_path, encoding="utf-8") as f:
            spec = yaml.safe_load(f)
        return jsonify(spec)

    # -----------
    # registra todos os blueprints
    # -----------
    for bp in [auth_bp, pedidos_bp, produtos_bp, unidades_bp,
               estoque_bp, pagamentos_bp, fidelidade_bp]:
        app.register_blueprint(bp)

    Base.metadata.create_all(bind=engine)

    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "servico": "Raizes do Nordeste API"}), 200

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "ROTA_NAO_ENCONTRADA", "message": "Endpoint nao existe.", "details": []}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({"error": "METODO_NAO_PERMITIDO", "message": "Metodo nao suportado.", "details": []}), 405

    @app.errorhandler(500)
    def internal_error(e):
        return jsonify({"error": "ERRO_INTERNO", "message": "Erro interno.", "details": []}), 500

    return app
