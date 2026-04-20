const SERVER = 'http://localhost:8000';

const dropzone  = document.getElementById('dropzone');
const fileInput = document.getElementById('fileInput');
const statusEl  = document.getElementById('status');
const resultEl  = document.getElementById('result');
const resetBar  = document.getElementById('resetBar');

document.getElementById('resetBtn').addEventListener('click', () => {
  dropzone.style.display = '';
  resetBar.style.display = 'none';
  resultEl.style.display = 'none';
  resultEl.innerHTML = '';
  setStatus('');
  fileInput.value = '';
});

// Open web UI
document.getElementById('openWeb').addEventListener('click', () => {
  chrome.tabs.create({ url: SERVER });
});

// Fetch provider label
fetch(`${SERVER}/`)
  .then(r => r.text())
  .then(html => {
    const m = html.match(/provider-(\w+)/);
    if (m) {
      const badge = document.getElementById('providerBadge');
      badge.textContent = m[1] === 'gemini' ? 'Gemini' : 'Claude';
      badge.style.background = m[1] === 'claude' ? '#d97706' : '#1e7e34';
    }
  })
  .catch(() => {});

// File browse
document.getElementById('browseBtn').addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', () => {
  if (fileInput.files[0]) uploadFile(fileInput.files[0]);
});

// Drag and drop
dropzone.addEventListener('dragover', e => {
  e.preventDefault();
  dropzone.classList.add('over');
});
dropzone.addEventListener('dragleave', () => dropzone.classList.remove('over'));
dropzone.addEventListener('drop', e => {
  e.preventDefault();
  dropzone.classList.remove('over');
  const file = e.dataTransfer.files[0];
  if (file && file.type === 'application/pdf') {
    uploadFile(file);
  } else {
    setStatus('PDF 파일만 지원합니다.', 'error');
  }
});

async function uploadFile(file) {
  dropzone.style.display = 'none';
  resetBar.style.display = 'none';
  setStatus('분석 중<span class="spinner"></span>', 'loading');
  resultEl.style.display = 'none';
  resultEl.innerHTML = '';

  const fd = new FormData();
  fd.append('file', file);

  try {
    const res = await fetch(`${SERVER}/analyze-pdf`, { method: 'POST', body: fd });
    const data = await res.json();
    if (data.error) {
      dropzone.style.display = '';
      setStatus('❌ ' + data.error, 'error');
    } else {
      setStatus('');
      resetBar.style.display = 'block';
      renderResult(data);
    }
  } catch (e) {
    dropzone.style.display = '';
    setStatus('❌ 서버 연결 실패 — 서버가 실행 중인지 확인하세요.', 'error');
  }
}

function setStatus(html, cls = '') {
  statusEl.innerHTML = html;
  statusEl.className = cls;
}

function esc(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function renderResult(data) {
  const { basic, analysis, quality, figures, authors } = data;

  const parts = [];

  // Paper title + meta chips
  const chips = [];
  if (basic.year)          chips.push(basic.year + '년');
  if (basic.venue)         chips.push(esc(basic.venue));
  if (basic.citationCount != null) chips.push(`인용 ${basic.citationCount}회`);

  const linksArr = [];
  if (basic.doi)     linksArr.push(`<a href="https://doi.org/${basic.doi}" target="_blank">DOI ↗</a>`);
  if (basic.arxivId) linksArr.push(`<a href="https://arxiv.org/abs/${basic.arxivId}" target="_blank">arXiv ↗</a>`);

  parts.push(`<div class="paper-title">${esc(basic.title) || '(제목 미추출)'}</div>`);
  if (chips.length) {
    parts.push(`<div class="meta-row">${chips.map(c => `<span class="meta-chip">${c}</span>`).join('')}</div>`);
  }
  if (linksArr.length) {
    parts.push(`<div class="meta-row">${linksArr.join('')}</div>`);
  }

  // Journal quality
  if (quality && quality.quartile) {
    const qKey = String(quality.quartile).trim().toLowerCase();
    const qClass = ['q1','q2','q3','q4'].includes(qKey) ? `q-${qKey}` : 'q-q4';
    const sjr = quality.sjr ? quality.sjr.replace(',', '.') : '—';
    parts.push(`
      <div class="quality-row">
        <div class="q-badge ${qClass}">${esc(quality.quartile)}</div>
        <div class="q-info">
          <div class="q-title">${esc(quality.matched_title) || '—'}</div>
          <div class="q-sjr">SJR ${sjr}</div>
        </div>
      </div>`);
  }

  // Analysis section
  if (analysis) {
    // Keywords
    const kwHtml = (analysis.keywords || [])
      .map(k => `<span class="kw-tag">${esc(k)}</span>`).join('');
    if (kwHtml) parts.push(`<div class="kw-row">${kwHtml}</div>`);

    // Relevance banner
    const relClass = analysis.relevance === '높음' ? 'rel-high'
      : analysis.relevance === '낮음' ? 'rel-low' : 'rel-mid';
    parts.push(`
      <div class="rel-banner ${relClass}">
        <span class="label">관련성 ${esc(analysis.relevance)}</span>
        <span>${esc(analysis.relevance_reason)}</span>
      </div>`);

    // Problem / Method / Conclusion
    const items = [
      { cls: 'prob', label: '문제',  text: analysis.problem },
      { cls: 'meth', label: '방법',  text: analysis.method },
      { cls: 'conc', label: '결론',  text: analysis.conclusion },
    ];
    for (const item of items) {
      parts.push(`
        <div class="acc-item ${item.cls}">
          <div class="acc-header">
            <span class="lbl">${item.label}</span>
          </div>
          <div class="detail">${esc(item.text)}</div>
        </div>`);
    }
  }

  // Authors
  if (authors && authors.length) {
    parts.push(`<div class="sec-label">👤 저자</div>`);
    const currentTitle = (basic.title || '').toLowerCase();
    const authorItems = authors.map(a => {
      const metaParts = [];
      if (a.hIndex != null)        metaParts.push(`h-index ${a.hIndex}`);
      if (a.citationCount != null) metaParts.push(`인용 ${a.citationCount.toLocaleString()}회`);
      const metaLine = metaParts.length
        ? `<div class="author-meta">${metaParts.join(' · ')}</div>`
        : '';
      const s2Link = a.authorId
        ? `<a class="author-link" href="https://www.semanticscholar.org/author/${a.authorId}" target="_blank">프로필 ↗</a>`
        : '';
      const paperItems = (a.topPapers || []).map(p => {
        const isCurrent = p.title && p.title.toLowerCase() === currentTitle;
        const titleHtml = isCurrent
          ? `<strong style="color:#4a6cf7;">${esc(p.title)} ★</strong>`
          : esc(p.title);
        return `<li>${titleHtml} <span class="cite">· 인용 ${p.citationCount ?? '?'}회</span></li>`;
      }).join('');
      const papersSection = paperItems
        ? `<ul class="top-papers">${paperItems}</ul>`
        : '';
      return `<div class="author-item">
        <div class="author-head"><span class="author-name">${esc(a.name)}</span>${s2Link}</div>
        ${metaLine}${papersSection}
      </div>`;
    }).join('');
    parts.push(authorItems);
  }

  // Figures (full-width stacked)
  if (figures && figures.length) {
    parts.push(`<div class="sec-label">📷 추출 이미지</div>`);
    const imgs = figures.slice(0, 3)
      .map(f => `<img class="fig-thumb" src="${f.data}" title="p.${f.page}" onclick="this.requestFullscreen?.()">`)
      .join('');
    parts.push(`<div class="figures-row">${imgs}</div>`);
  }

  resultEl.innerHTML = parts.join('');
  resultEl.style.display = 'block';
}
