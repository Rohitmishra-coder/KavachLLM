import os
import torch
from flask import Flask, request, jsonify, render_template_string
from transformers import AutoTokenizer, AutoModelForSequenceClassification, AutoModelForCausalLM

app = Flask(__name__)

# ==================== CONFIG - LOAD TOKENS FROM ENVIRONMENT VARIABLES ====================
HF_REPO = "RohitMishra2005/KavachLLM"
HF_TOKEN = os.getenv("HF_TOKEN")  # ← Set this in Render dashboard
CHECKPOINT_SUBFOLDER = "detector_checkpoints/checkpoint-186000"  # ← your latest
MITIGATOR_MODEL = "Qwen/Qwen2.5-Coder-7B-Instruct"

# Check if token is available (important for production)
if not HF_TOKEN:
    print("WARNING: HF_TOKEN environment variable is missing! Set it in Render dashboard.")
    # You can continue with public models or fail gracefully
    HF_TOKEN = None

# ==================== DEVICE ====================
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Using device: {device}")

# ==================== LOAD MODELS ====================
tokenizer = model = mitigator = mitigator_tokenizer = None

try:
    print("Loading detector tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(
        HF_REPO,
        subfolder="tokenizer",
        token=HF_TOKEN,
        trust_remote_code=True
    )
    print("Loading detector model...")
    model = AutoModelForSequenceClassification.from_pretrained(
        HF_REPO,
        subfolder=CHECKPOINT_SUBFOLDER,
        num_labels=6,
        token=HF_TOKEN,
        device_map="auto",
        torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
        trust_remote_code=True
    )
    model.eval()
    print("Detector loaded successfully")
except Exception as e:
    print(f"Failed to load detector: {e}")

try:
    print("Loading mitigator...")
    mitigator_tokenizer = AutoTokenizer.from_pretrained(
        MITIGATOR_MODEL,
        token=HF_TOKEN,
        trust_remote_code=True
    )
    if mitigator_tokenizer.pad_token is None:
        mitigator_tokenizer.pad_token = mitigator_tokenizer.eos_token
    mitigator = AutoModelForCausalLM.from_pretrained(
        MITIGATOR_MODEL,
        token=HF_TOKEN,
        trust_remote_code=True,
        torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
        device_map="auto"
    )
    mitigator.eval()
    print("Mitigator loaded successfully")
except Exception as e:
    print(f"Failed to load mitigator: {e}")

ID2LABEL = {
    0: "safe", 1: "sql_injection", 2: "path_traversal",
    3: "xss", 4: "command_injection", 5: "hardcoded_credentials"
}

# ==================== MODERN UI (Tailwind) ====================
HTML = """
<!DOCTYPE html>
<html lang="en" class="scroll-smooth">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kavach LLM - Secure Code Guardian</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
</head>
<body class="bg-gradient-to-br from-indigo-50 via-white to-purple-50 dark:from-gray-900 dark:via-gray-900 dark:to-indigo-950 text-gray-900 dark:text-gray-100 min-h-screen transition-colors duration-300">
    <header class="bg-gradient-to-r from-indigo-600 via-purple-600 to-pink-600 text-white shadow-2xl">
        <div class="max-w-6xl mx-auto px-6 py-8 text-center">
            <h1 class="text-5xl md:text-6xl font-extrabold tracking-tight drop-shadow-lg">
                <i class="fas fa-shield-halved mr-3 text-yellow-300"></i>Kavach LLM
            </h1>
            <p class="mt-3 text-xl md:text-2xl opacity-90 font-light">
                AI-Powered Vulnerability Detection & Instant Secure Fixes
            </p>
        </div>
    </header>

    <main class="max-w-5xl mx-auto px-6 py-12">
        <div class="bg-white/80 dark:bg-gray-800/80 backdrop-blur-lg rounded-3xl shadow-2xl p-8 md:p-12 border border-indigo-200 dark:border-indigo-800">
            <form id="scanForm" class="space-y-8">
                <div>
                    <label for="code" class="block text-xl font-semibold mb-3 flex items-center gap-2">
                        <i class="fas fa-code text-indigo-600 dark:text-indigo-400"></i>
                        Paste Your Code
                    </label>
                    <textarea id="code" name="code" rows="10" required placeholder="Write or paste your code here..." class="w-full p-5 border border-gray-300 dark:border-gray-600 rounded-xl bg-white/50 dark:bg-gray-700/50 focus:ring-4 focus:ring-indigo-500 focus:border-indigo-500 transition shadow-inner font-mono text-sm"></textarea>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                        <label for="language" class="block text-xl font-semibold mb-3 flex items-center gap-2">
                            <i class="fas fa-language text-purple-600 dark:text-purple-400"></i>
                            Programming Language
                        </label>
                        <select id="language" name="language" class="w-full p-4 border border-gray-300 dark:border-gray-600 rounded-xl bg-white/50 dark:bg-gray-700/50 focus:ring-4 focus:ring-indigo-500 transition shadow-sm">
                            <option value="python">Python</option>
                            <option value="javascript">JavaScript</option>
                            <option value="java">Java</option>
                            <option value="php">PHP</option>
                            <option value="c">C / C++</option>
                            <option value="go">Go</option>
                            <option value="other">Other</option>
                        </select>
                    </div>

                    <div class="flex items-end">
                        <button type="submit" class="w-full py-5 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white font-bold text-lg rounded-xl shadow-lg hover:shadow-2xl transform hover:scale-[1.02] transition-all duration-300 flex items-center justify-center gap-3">
                            <i class="fas fa-shield-halved text-xl"></i> Scan & Secure
                        </button>
                    </div>
                </div>
            </form>
        </div>

        <div id="result" class="mt-12 bg-white/80 dark:bg-gray-800/80 backdrop-blur-lg rounded-3xl shadow-2xl p-8 border border-indigo-200 dark:border-indigo-800 hidden">
            <h2 class="text-3xl font-bold mb-6 text-center text-indigo-700 dark:text-indigo-300">Scan Results</h2>
            <div id="detection" class="text-xl mb-8"></div>
            <div id="fix" class="mt-6"></div>
        </div>
    </main>

    <script>
        const form = document.getElementById('scanForm');
        const resultDiv = document.getElementById('result');

        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            resultDiv.classList.remove('hidden');
            resultDiv.innerHTML = '<div class="text-center py-10"><i class="fas fa-spinner fa-spin text-5xl text-indigo-600"></i><p class="mt-4 text-lg">Analyzing code...</p></div>';

            const formData = new FormData(form);
            const data = { code: formData.get('code'), language: formData.get('language') };

            try {
                const res = await fetch('/scan', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });

                const result = await res.json();

                let detectionHTML = `
                    <div class="flex items-center justify-center gap-4 text-2xl font-bold">
                        <span class="${result.prediction === 'safe' ? 'text-green-600' : 'text-red-600'}">
                            ${result.prediction === 'safe' ? '✓ Safe' : '⚠️ Vulnerable'}
                        </span>
                        <span class="text-gray-600 dark:text-gray-400">(${result.confidence}% confidence)</span>
                    </div>
                    <p class="mt-4 text-center text-lg">${result.details}</p>
                `;

                let fixHTML = '';
                if (result.fixed_code && result.fixed_code !== "No fix generated.") {
                    fixHTML = `
                        <h3 class="text-2xl font-semibold mt-10 mb-4 text-center text-indigo-700 dark:text-indigo-300">Secure Fixed Code</h3>
                        <pre class="bg-gray-900 text-green-400 p-6 rounded-xl overflow-x-auto text-sm font-mono leading-relaxed shadow-inner">${result.fixed_code}</pre>
                    `;
                }

                resultDiv.innerHTML = detectionHTML + fixHTML;
            } catch (err) {
                resultDiv.innerHTML = `<p class="text-center text-red-600 text-xl">Error: ${err.message}</p>`;
            }
        });
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/scan', methods=['POST'])
def scan():
    if tokenizer is None or model is None:
        return jsonify({"error": "Detector model not loaded"}), 500

    data = request.json
    code = data.get('code', '')
    language = data.get('language', 'python')

    if not code.strip():
        return jsonify({"error": "No code provided"}), 400

    try:
        inputs = tokenizer([code], padding=True, truncation=True, max_length=256, return_tensors="pt").to(device)
        with torch.no_grad():
            outputs = model(**inputs)
            probs = torch.softmax(outputs.logits, dim=-1).cpu().numpy()[0]
            pred_id = int(probs.argmax())
            confidence = float(probs[pred_id] * 100)
            pred_label = ID2LABEL[pred_id]

        if pred_id == 0:
            return jsonify({
                "prediction": "safe",
                "confidence": f"{confidence:.1f}",
                "details": "No vulnerabilities detected.",
                "fixed_code": code
            })

        fixed_code = "Mitigator not loaded."
        if mitigator is not None and mitigator_tokenizer is not None:
            vuln_type = ID2LABEL[pred_id]
            prompt = f"""Fix the {vuln_type} vulnerability in this {language} code. Preserve functionality.

<vulnerable_code>
{code}
</vulnerable_code>

<fixed_code>"""

            mit_inputs = mitigator_tokenizer(prompt, return_tensors="pt").to(device)
            with torch.no_grad():
                output = mitigator.generate(
                    **mit_inputs,
                    max_new_tokens=300,
                    temperature=0.1,
                    top_p=0.95,
                    do_sample=True,
                    repetition_penalty=1.1,
                    pad_token_id=mitigator_tokenizer.eos_token_id
                )
            generated = mitigator_tokenizer.decode(output[0], skip_special_tokens=True)
            if "<fixed_code>" in generated:
                fixed_code = generated.split("<fixed_code>")[-1].strip()
            else:
                fixed_code = generated[len(prompt):].strip() or "No fix generated."

        return jsonify({
            "prediction": pred_label,
            "confidence": f"{confidence:.1f}",
            "details": f"Detected {pred_label}",
            "fixed_code": fixed_code
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==================== RUN FOR PRODUCTION (Render) ====================
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))  # Render sets PORT env var
    app.run(host="0.0.0.0", port=port, debug=False)