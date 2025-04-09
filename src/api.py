import logging
from flask import Flask, request, jsonify, render_template
from .rag_pipeline import get_rag_response

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/query', methods=['POST'])
def handle_query():
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    question = data.get('question')

    if not question or not isinstance(question, str) or not question.strip():
        return jsonify({"error": "Missing or invalid 'question' field in JSON body"}), 400

    app.logger.info(f"Query received: '{question}'")

    try:
        answer = get_rag_response(question)
        app.logger.info(f"Answer (truncated): '{answer[:100]}...'")
        return jsonify({"answer": answer})
    except Exception as e:
        app.logger.exception(f"Error handling query: {e}")
        return jsonify({"error": "Internal server error."}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
