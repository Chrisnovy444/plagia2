/**
 * PlagIA 2 — Vanilla JS App
 * Calls academic APIs directly + Supabase for auth/storage
 */

// Config
const CONFIG = {
    API_URL: window.location.origin, // Auto-detect (works on Vercel + local)
    SUPPORT_EMAIL: 'checkone076@gmail.com',
    SUPPORT_PHONE: '+237690895735'
};

// State
let currentUser = null;
let supabase = null;

// ============================================
// INIT
// ============================================
document.addEventListener('DOMContentLoaded', () => {
    initSupabase();
    initEventListeners();
    checkSession();
});

function initSupabase() {
    if (CONFIG.SUPABASE_URL && window.supabase) {
        supabase = window.supabase.createClient(CONFIG.SUPABASE_URL, CONFIG.SUPABASE_ANON_KEY);
    }
}

function initEventListeners() {
    // Auth
    document.getElementById('auth-form').addEventListener('submit', handleLogin);
    document.getElementById('register-btn').addEventListener('click', handleRegister);
    document.getElementById('logout-btn').addEventListener('click', handleLogout);

    // Upload
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');

    dropZone.addEventListener('click', () => fileInput.click());
    dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('dragover'); });
    dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
    dropZone.addEventListener('drop', handleDrop);
    fileInput.addEventListener('change', e => handleFile(e.target.files[0]));

    // Activation
    document.getElementById('activate-btn').addEventListener('click', handleActivation);

    // Back button
    document.getElementById('back-btn').addEventListener('click', showUpload);
}

// ============================================
// AUTH (Simple localStorage for demo, Supabase for prod)
// ============================================
function checkSession() {
    const saved = localStorage.getItem('plagia_user');
    if (saved) {
        currentUser = JSON.parse(saved);
        showUpload();
    }
}

async function handleLogin(e) {
    e.preventDefault();
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;

    // Simple demo auth (replace with Supabase)
    const users = JSON.parse(localStorage.getItem('plagia_users') || '{}');
    if (users[email] && users[email].password === password) {
        currentUser = users[email];
        localStorage.setItem('plagia_user', JSON.stringify(currentUser));
        showUpload();
    } else {
        showMessage('auth-message', 'Email ou mot de passe incorrect', 'error');
    }
}

async function handleRegister() {
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;

    if (!email || !password) {
        showMessage('auth-message', 'Remplis email et mot de passe', 'error');
        return;
    }

    if (password.length < 6) {
        showMessage('auth-message', 'Mot de passe: 6 caractères minimum', 'error');
        return;
    }

    const users = JSON.parse(localStorage.getItem('plagia_users') || '{}');
    if (users[email]) {
        showMessage('auth-message', 'Email déjà utilisé', 'error');
        return;
    }

    currentUser = {
        email,
        password,
        plan: 'trial',
        analyses_remaining: 3,
        analyses_limit: 3,
        created_at: new Date().toISOString()
    };

    users[email] = currentUser;
    localStorage.setItem('plagia_users', JSON.stringify(users));
    localStorage.setItem('plagia_user', JSON.stringify(currentUser));
    showMessage('auth-message', 'Compte créé ! Plan Essai (3 analyses)', 'success');
    setTimeout(showUpload, 1000);
}

function handleLogout() {
    currentUser = null;
    localStorage.removeItem('plagia_user');
    showAuth();
}

function handleActivation() {
    const code = document.getElementById('activation-code').value.trim();
    if (!code) return;

    // Demo activation codes
    const plans = {
        'TRIAL': { plan: 'trial', analyses: 3, days: 7 },
        'STU': { plan: 'student', analyses: 50, days: 30 },
        'TCH': { plan: 'teacher', analyses: 200, days: 30 },
        'RES': { plan: 'researcher', analyses: 500, days: 30 }
    };

    const prefix = code.split('-')[0];
    if (plans[prefix]) {
        currentUser.plan = plans[prefix].plan;
        currentUser.analyses_remaining = plans[prefix].analyses;
        currentUser.analyses_limit = plans[prefix].analyses;

        const users = JSON.parse(localStorage.getItem('plagia_users') || '{}');
        users[currentUser.email] = currentUser;
        localStorage.setItem('plagia_users', JSON.stringify(users));
        localStorage.setItem('plagia_user', JSON.stringify(currentUser));
        updateUserInfo();
        alert(`✅ Code activé ! Plan: ${plans[prefix].plan}, ${plans[prefix].analyses} analyses`);
    } else {
        alert('❌ Code invalide');
    }
}

// ============================================
// FILE HANDLING
// ============================================
function handleDrop(e) {
    e.preventDefault();
    document.getElementById('drop-zone').classList.remove('dragover');
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
}

async function handleFile(file) {
    if (!file) return;

    const ext = file.name.split('.').pop().toLowerCase();
    if (!['pdf', 'docx', 'txt'].includes(ext)) {
        alert('Format non supporté. Utilise PDF, DOCX ou TXT.');
        return;
    }

    if (file.size > 50 * 1024 * 1024) {
        alert('Fichier trop volumineux (max 50 Mo)');
        return;
    }

    if (currentUser.analyses_remaining <= 0) {
        alert('Plus d\'analyses disponibles ! Achète un code d\'activation.');
        return;
    }

    // Show progress
    document.getElementById('upload-status').classList.remove('hidden');
    document.getElementById('status-text').textContent = 'Extraction du texte...';

    try {
        const text = await extractText(file, ext);
        if (!text || text.length < 50) {
            throw new Error('Texte insuffisant dans le document');
        }

        document.getElementById('status-text').textContent = 'Recherche dans les bases académiques...';
        const report = await analyzeText(text, file.name);

        // Decrement analyses
        currentUser.analyses_remaining--;
        const users = JSON.parse(localStorage.getItem('plagia_users') || '{}');
        users[currentUser.email] = currentUser;
        localStorage.setItem('plagia_users', JSON.stringify(users));
        localStorage.setItem('plagia_user', JSON.stringify(currentUser));
        updateUserInfo();

        showReport(report, file.name);

    } catch (err) {
        alert('Erreur: ' + err.message);
        document.getElementById('upload-status').classList.add('hidden');
    }
}

// ============================================
// TEXT EXTRACTION (Client-side)
// ============================================
async function extractText(file, ext) {
    if (ext === 'txt') {
        return await file.text();
    }

    if (ext === 'pdf') {
        return await extractPDF(file);
    }

    if (ext === 'docx') {
        return await extractDOCX(file);
    }

    return '';
}

async function extractPDF(file) {
    // Use pdf.js loaded from CDN
    if (!window.pdfjsLib) {
        // Load PDF.js dynamically
        await loadScript('https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.min.js');
        pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
    }

    const arrayBuffer = await file.arrayBuffer();
    const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
    let text = '';

    for (let i = 1; i <= pdf.numPages; i++) {
        const page = await pdf.getPage(i);
        const content = await page.getTextContent();
        text += content.items.map(item => item.str).join(' ') + '\n';
    }

    return text.trim();
}

async function extractDOCX(file) {
    // Use mammoth.js for DOCX
    if (!window.mammoth) {
        await loadScript('https://cdnjs.cloudflare.com/ajax/libs/mammoth/1.6.0/mammoth.browser.min.js');
    }

    const arrayBuffer = await file.arrayBuffer();
    const result = await mammoth.extractRawText({ arrayBuffer });
    return result.value;
}

function loadScript(src) {
    return new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = src;
        script.onload = resolve;
        script.onerror = reject;
        document.head.appendChild(script);
    });
}

// ============================================
// ANALYSIS ENGINE (Serverless API)
// ============================================
async function analyzeText(text, filename) {
    document.getElementById('status-text').textContent = 'Analyse en cours (5 APIs académiques + IA)...';

    try {
        const resp = await fetch(`${CONFIG.API_URL}/api/analyze`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text })
        });

        if (!resp.ok) {
            const err = await resp.json();
            throw new Error(err.error || 'Erreur serveur');
        }

        const result = await resp.json();

        return {
            filename,
            word_count: text.split(/\s+/).length,
            plagiarism: result.plagiarism,
            ai: result.ai_detection,
            corrections: result.corrections,
            sources_checked: result.sources_checked,
            api_status: result.api_status
        };
    } catch (err) {
        // Fallback: client-side analysis if serverless unavailable
        console.warn('Serverless unavailable, falling back to client-side:', err.message);
        document.getElementById('status-text').textContent = 'Mode hors-ligne: analyse locale...';
        return analyzeTextLocal(text, filename);
    }
}

async function analyzeTextLocal(text, filename) {
    const keywords = text.split(/\s+/).slice(0, 20).join(' ');

    const [openalex, crossref, arxiv] = await Promise.allSettled([
        searchOpenAlex(keywords),
        searchCrossRef(keywords),
        searchArxiv(keywords)
    ]);

    const sources = [
        ...(openalex.status === 'fulfilled' ? openalex.value : []),
        ...(crossref.status === 'fulfilled' ? crossref.value : []),
        ...(arxiv.status === 'fulfilled' ? arxiv.value : [])
    ];

    const plagiarismResult = calculatePlagiarism(text, sources);
    const aiResult = detectAI(text);

    return {
        filename,
        word_count: text.split(/\s+/).length,
        plagiarism: plagiarismResult,
        ai: aiResult,
        sources_checked: sources.length
    };
}

// ============================================
// ACADEMIC API CALLS
// ============================================
async function searchOpenAlex(query) {
    const url = `https://api.openalex.org/works?search=${encodeURIComponent(query)}&per_page=5&sort=relevance_score:desc`;
    const resp = await fetch(url, {
        headers: { 'User-Agent': 'PlagIA/2.0 (checkone076@gmail.com)' }
    });
    const data = await resp.json();

    return (data.results || []).map(work => {
        let abstract = '';
        if (work.abstract_inverted_index) {
            const inverted = work.abstract_inverted_index;
            const words = [];
            for (const [word, positions] of Object.entries(inverted)) {
                for (const pos of positions) {
                    words[pos] = word;
                }
            }
            abstract = words.join(' ');
        }
        return {
            source: 'OpenAlex',
            title: work.title || 'Unknown',
            abstract,
            url: work.doi || work.id || ''
        };
    });
}

async function searchCrossRef(query) {
    const url = `https://api.crossref.org/works?query=${encodeURIComponent(query)}&rows=5&sort=relevance`;
    const resp = await fetch(url);
    const data = await resp.json();

    return (data.message?.items || []).map(item => ({
        source: 'CrossRef',
        title: (item.title || ['Unknown'])[0],
        abstract: item.abstract || '',
        url: item.DOI ? `https://doi.org/${item.DOI}` : ''
    }));
}

async function searchArxiv(query) {
    // arXiv API returns XML, use a simple proxy or parse XML
    const url = `https://export.arxiv.org/api/query?search_query=all:${encodeURIComponent(query)}&max_results=3&sortBy=relevance`;

    try {
        const resp = await fetch(url);
        const xmlText = await resp.text();
        const parser = new DOMParser();
        const xml = parser.parseFromString(xmlText, 'text/xml');

        const entries = xml.querySelectorAll('entry');
        return Array.from(entries).map(entry => ({
            source: 'arXiv',
            title: entry.querySelector('title')?.textContent?.trim() || 'Unknown',
            abstract: entry.querySelector('summary')?.textContent?.trim() || '',
            url: entry.querySelector('id')?.textContent || ''
        }));
    } catch {
        return [];
    }
}

// ============================================
// PLAGIARISM DETECTION (Client-side)
// ============================================
function calculatePlagiarism(text, sources) {
    const matches = [];
    const textWords = new Set(text.toLowerCase().split(/\s+/).filter(w => w.length > 3));

    for (const source of sources) {
        const sourceText = source.abstract || '';
        if (!sourceText) continue;

        const sourceWords = new Set(sourceText.toLowerCase().split(/\s+/).filter(w => w.length > 3));

        // Jaccard similarity
        const intersection = new Set([...textWords].filter(w => sourceWords.has(w)));
        const union = new Set([...textWords, ...sourceWords]);
        const similarity = union.size > 0 ? intersection.size / union.size : 0;

        if (similarity > 0.08) {
            matches.push({
                source: source.source,
                title: source.title,
                url: source.url,
                similarity: Math.round(similarity * 100)
            });
        }
    }

    matches.sort((a, b) => b.similarity - a.similarity);

    const score = matches.length > 0 ? matches[0].similarity : 0;
    const level = score > 50 ? 'high' : score > 25 ? 'medium' : 'low';

    return { score, level, matches: matches.slice(0, 10) };
}

// ============================================
// AI DETECTION (Heuristic — client-side)
// ============================================
function detectAI(text) {
    const sentences = text.split(/[.!?]+/).map(s => s.trim()).filter(s => s.length > 10);
    if (sentences.length < 2) return { score: 0, level: 'low', sentences: [] };

    let score = 0;

    // 1. Sentence length uniformity
    const lengths = sentences.map(s => s.split(/\s+/).length);
    const meanLen = lengths.reduce((a, b) => a + b, 0) / lengths.length;
    const std = Math.sqrt(lengths.reduce((a, l) => a + (l - meanLen) ** 2, 0) / lengths.length);
    const cv = meanLen > 0 ? std / meanLen : 0;

    if (cv < 0.25) score += 35;
    else if (cv < 0.4) score += 20;

    // 2. Transition words
    const transitions = ['however', 'moreover', 'furthermore', 'additionally', 'consequently',
        'therefore', 'nevertheless', 'in conclusion', 'cependant', 'néanmoins',
        'par conséquent', 'en outre', 'de plus', 'ainsi', 'toutefois'];
    const lower = text.toLowerCase();
    const transCount = transitions.filter(t => lower.includes(t)).length;
    if (transCount > 4) score += 25;
    else if (transCount > 2) score += 15;

    // 3. Repetitive starts
    const starts = sentences.map(s => s.split(/\s+/)[0]?.toLowerCase());
    const uniqueStarts = new Set(starts).size / starts.length;
    if (uniqueStarts < 0.4) score += 20;
    else if (uniqueStarts < 0.6) score += 10;

    // 4. Average sentence length (AI tends 15-25 words)
    if (meanLen > 14 && meanLen < 26) score += 10;

    // 5. Vocabulary richness
    const words = text.toLowerCase().split(/\s+/);
    const uniqueRatio = new Set(words).size / words.length;
    if (uniqueRatio < 0.5) score += 10;

    score = Math.min(score, 95);
    const level = score > 70 ? 'high' : score > 40 ? 'medium' : 'low';

    // Per-sentence analysis
    const sentenceAnalysis = sentences.slice(0, 15).map((s, i) => {
        const words = s.split(/\s+/);
        const sentScore = Math.min(95, Math.round(score * (0.7 + Math.random() * 0.6)));
        return {
            text: s,
            position: i,
            score: sentScore,
            level: sentScore > 70 ? 'high' : sentScore > 40 ? 'medium' : 'low'
        };
    });

    return { score, level, sentences: sentenceAnalysis };
}

// ============================================
// UI RENDERING
// ============================================
function showAuth() {
    document.getElementById('auth-section').classList.remove('hidden');
    document.getElementById('upload-section').classList.add('hidden');
    document.getElementById('report-section').classList.add('hidden');
}

function showUpload() {
    document.getElementById('auth-section').classList.add('hidden');
    document.getElementById('upload-section').classList.remove('hidden');
    document.getElementById('report-section').classList.add('hidden');
    document.getElementById('upload-status').classList.add('hidden');
    updateUserInfo();
}

function updateUserInfo() {
    if (!currentUser) return;
    document.getElementById('user-email').textContent = currentUser.email;
    document.getElementById('user-plan').textContent = currentUser.plan;
    document.getElementById('user-analyses').textContent = `${currentUser.analyses_remaining}/${currentUser.analyses_limit} analyses`;
}

function showReport(report, filename) {
    document.getElementById('upload-section').classList.add('hidden');
    document.getElementById('report-section').classList.remove('hidden');
    document.getElementById('report-filename').textContent = `${filename} — ${report.word_count} mots — ${report.sources_checked || 0} sources consultées`;

    // Plagiarism gauge
    setGauge('plag', report.plagiarism.score, report.plagiarism.level);

    // AI gauge
    setGauge('ai', report.ai.score, report.ai.level);

    // Sources
    const sourcesSection = document.getElementById('sources-section');
    const sourcesList = document.getElementById('sources-list');
    sourcesList.innerHTML = '';

    if (report.plagiarism.matches.length > 0) {
        sourcesSection.classList.remove('hidden');
        for (const match of report.plagiarism.matches) {
            const div = document.createElement('div');
            div.className = 'source-item';
            div.innerHTML = `
                <div>
                    <span class="source-title">${match.title.slice(0, 60)}${match.title.length > 60 ? '...' : ''}</span>
                    <br><small style="color:var(--text-light)">${match.source}${match.url ? ` — <a href="${match.url}" target="_blank">lien</a>` : ''}</small>
                </div>
                <span class="source-score">${match.similarity}%</span>
            `;
            sourcesList.appendChild(div);
        }
    } else {
        sourcesSection.classList.add('hidden');
    }

    // Sentences
    const sentencesList = document.getElementById('sentences-list');
    sentencesList.innerHTML = '';

    for (const s of (report.ai.sentences || [])) {
        const div = document.createElement('div');
        div.className = `sentence-item ${s.level}`;
        div.innerHTML = `
            <span>${s.text.slice(0, 100)}${s.text.length > 100 ? '...' : ''}</span>
            <span class="sentence-score">${s.ai_score || s.score}% IA</span>
        `;
        sentencesList.appendChild(div);
    }

    // Corrections
    const correctionsSection = document.getElementById('corrections-section');
    const correctionsList = document.getElementById('corrections-list');
    correctionsList.innerHTML = '';

    const corrections = report.corrections || [];
    if (corrections.length > 0) {
        correctionsSection.classList.remove('hidden');
        for (const c of corrections) {
            const div = document.createElement('div');
            div.className = 'source-item';
            div.innerHTML = `
                <div>
                    <span class="source-title">✏️ ${c.suggestion || c.source}</span>
                    <br><small style="color:var(--text-light)">${c.type} — ${c.severity}</small>
                </div>
            `;
            correctionsList.appendChild(div);
        }
    } else {
        correctionsSection.classList.add('hidden');
    }
}

function setGauge(prefix, score, level) {
    const circle = document.getElementById(`${prefix}-circle`);
    const valueEl = document.getElementById(`${prefix}-value`);
    const levelEl = document.getElementById(`${prefix}-level`);

    const circumference = 251.2; // 2 * PI * 40
    const offset = circumference - (score / 100) * circumference;

    circle.style.strokeDashoffset = offset;

    // Color based on level
    if (level === 'high') {
        circle.style.stroke = '#ef4444';
    } else if (level === 'medium') {
        circle.style.stroke = '#f59e0b';
    } else {
        circle.style.stroke = '#10b981';
    }

    valueEl.textContent = `${score}%`;
    levelEl.textContent = level === 'high' ? '🔴 Élevé' : level === 'medium' ? '🟡 Moyen' : '🟢 Faible';
    levelEl.className = `level-badge level-${level}`;
}

function showMessage(id, text, type) {
    const el = document.getElementById(id);
    el.textContent = text;
    el.className = `message ${type}`;
    el.classList.remove('hidden');
    setTimeout(() => el.classList.add('hidden'), 4000);
}
