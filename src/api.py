# src/api.py
import logging
from flask import Flask, request, jsonify, render_template
# CHANGE THIS IMPORT if you named the file rag_pipeline_pinecone.py
from .rag_pipeline import get_rag_response

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

app = Flask(__name__)

@app.route('/')
def home():
    # ... (keep your existing code)
    return render_template('index.html')


@app.route('/query', methods=['POST'])
def handle_query():
    # ... (keep your existing code)
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    question = data.get('question')

    if not question or not isinstance(question, str) or not question.strip():
        return jsonify({"error": "Missing or invalid 'question' field in JSON body"}), 400

    app.logger.info(f"Query received: '{question}'")

    try:
        answer = get_rag_response(question) # This now calls the Pinecone version
        app.logger.info(f"Answer generated (truncated): '{answer[:100]}...'")
        return jsonify({"answer": answer})
    except Exception as e:
        app.logger.exception(f"Error handling query: {e}")
        return jsonify({"error": "Internal server error processing your request."}), 500


if __name__ == '__main__':
    # Consider setting debug=False for deployment
    app.run(debug=True, host='0.0.0.0', port=5000)