from app import create_app

# -----------
# entrypoint da api
# rodar com: python run.py
# acesse em http://localhost:5000
# swagger em http://localhost:5000/docs/
# -----------

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
