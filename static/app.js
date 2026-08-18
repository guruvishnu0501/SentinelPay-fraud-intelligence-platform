const form = document.getElementById('txForm');
const result = document.getElementById('result');
const pdfBtn = document.getElementById('pdfBtn');

function getPayload() {
  const fd = new FormData(form);
  const o = Object.fromEntries(fd.entries());
  ['amount_inr', 'customer_lat', 'customer_lon', 'merchant_lat', 'merchant_lon'].forEach(k => {
    o[k] = Number(o[k]);
  });
  o.card_id = String(o.card_id).trim();
  o.trans_date_trans_time = o.trans_date_trans_time.replace('T', ' ') + ':00';
  return o;
}

function esc(val) {
  const str = val == null ? '' : String(val);
  return str.replace(/[&<>"']/g, m => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[m]));
}

function buildDynamicExplanation(r) {
  const level = r.risk_level || 'LOW';
  const reasons = r.reasons || [];
  if (level === 'LOW' || !reasons.length) {
    return "No material anomaly evidence was detected. The transaction is consistent with available behavioral and contextual signals.";
  }
  if (level === 'MEDIUM') {
    return "The transaction shows elevated risk due to a combination of transaction value and contextual anomalies: " + reasons.join(", ") + ". Step-up authentication is recommended before authorization.";
  }
  return "Multiple independent risk signals converge on elevated fraud risk: " + reasons.join(", ") + ". Immediate transaction decline/block is recommended.";
}

function renderResult(r, p) {
  result.classList.remove('hidden');
  const levelClass = (r.risk_level || 'LOW').toLowerCase();
  const explanation = buildDynamicExplanation(r);
  
  const ctx = r.behavioral_context || {};

  const txContext = {
    'Amount Percentile': ctx.amount_percentile != null ? (ctx.amount_percentile * 100).toFixed(1) + '%' : null,
    'Merchant Distance': ctx.merchant_distance_km != null ? ctx.merchant_distance_km.toFixed(1) + ' km' : null,
    'Transaction Hour': ctx.hour != null ? ctx.hour + ':00' : null
  };

  const histContext = {
    'History State': ctx.card_transaction_count_before != null && ctx.card_transaction_count_before > 0 ? `${ctx.card_transaction_count_before} prior transactions` : 'Cold Start (0 prior txns)',
    'Amount Ratio to Card Avg': ctx.amount_ratio_to_card_avg != null ? ctx.amount_ratio_to_card_avg.toFixed(2) + 'x' : null,
    'Txns Last 1h': ctx.txns_last_1h,
    'Txns Last 24h': ctx.txns_last_24h,
    'Hours Since Previous': ctx.hours_since_previous != null ? ctx.hours_since_previous.toFixed(1) + ' hrs' : null
  };

  const geoContext = {
    'New City': ctx.new_city != null ? (ctx.new_city ? 'Yes (First time)' : 'No (Known city)') : null,
    'New Device': ctx.new_device != null ? (ctx.new_device ? 'Yes (Unrecognized)' : 'No (Known device)') : null,
    'Previous Location Distance': ctx.previous_location_distance_km != null ? ctx.previous_location_distance_km.toFixed(1) + ' km' : null,
    'Implied Travel Speed': ctx.implied_travel_speed_kmh != null ? ctx.implied_travel_speed_kmh.toFixed(1) + ' km/h' : null
  };

  const renderGroup = (title, groupObj) => `
    <div style="margin-bottom: 14px;">
      <div style="font-size: 13px; font-weight: 700; color: var(--accent); margin-bottom: 6px;">${title}</div>
      <div class="table-container">
        <table>
          <tbody>
            ${Object.entries(groupObj).map(([k, v]) => `
              <tr>
                <td style="width: 50%;"><b>${esc(k)}</b></td>
                <td>${v != null ? esc(v) : '<span style="color: var(--text-dim); font-style: italic;">Unavailable — Cold Start</span>'}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;

  result.innerHTML = `
    <div class="result-header">
      <div>
        <div class="decision-title">${esc(r.decision)}</div>
        <div style="font-size: 15px; color: var(--text-muted); margin-top: 4px;">
          Recommended Action: <b style="color: var(--text-main);">${esc(r.recommended_action)}</b>
        </div>
      </div>
      <div style="text-align: right;">
        <div class="badge-risk ${levelClass}">[ ${esc(r.risk_level)} RISK ]</div>
        <div style="font-size: 22px; font-weight: 800; margin-top: 6px;">
          Score: ${r.operational_risk_score.toFixed(1)} <span style="font-size: 13px; color: var(--text-muted);">/ 100</span>
        </div>
      </div>
    </div>

    <div class="kpi-grid" style="margin-bottom: 24px;">
      <div class="kpi-card">
        <div class="label">Fraud Probability</div>
        <div class="value">${(r.ml_fraud_probability * 100).toFixed(2)}%</div>
      </div>
      <div class="kpi-card">
        <div class="label">Business Evidence</div>
        <div class="value">${r.business_evidence_score} <span style="font-size: 13px; color: var(--text-muted);">/ 100</span></div>
      </div>
      <div class="kpi-card">
        <div class="label">Evidence Families</div>
        <div class="value">${r.evidence_family_count}</div>
      </div>
    </div>

    <div class="section-title">Decision Explanation</div>
    <p style="font-size: 14px; line-height: 1.6; color: var(--text-main); background: var(--bg-card); padding: 14px; border-radius: 8px; border-left: 3px solid var(--primary); margin-bottom: 20px;">
      "${esc(explanation)}"
    </p>

    <div class="section-title">Triggered Risk Factors</div>
    <div style="margin-bottom: 24px; display: flex; flex-wrap: wrap; gap: 8px;">
      ${r.reasons && r.reasons.length ? r.reasons.map(x => `
        <div style="background: var(--bg-card); border: 1px solid var(--border); padding: 8px 14px; border-radius: 8px; font-size: 13px; font-weight: 500;">
          ⚠️ ${esc(x)}
        </div>
      `).join('') : '<div style="color: var(--text-muted); font-size: 14px;">No anomaly factors triggered</div>'}
    </div>

    <div class="section-title">Behavioral &amp; Contextual Signals</div>
    ${renderGroup('Transaction Context', txContext)}
    ${renderGroup('Historical Behavior', histContext)}
    ${renderGroup('Geographic & Device Context', geoContext)}
  `;

  try {
    sessionStorage.setItem('sentinelpay_last_analysis', JSON.stringify(r));
  } catch (e) {}
}

if (form) {
  form.addEventListener('submit', async e => {
    e.preventDefault();
    const btn = document.getElementById('analyzeBtn');
    if (btn) {
      btn.disabled = true;
      btn.textContent = 'Analyzing…';
    }
    
    try {
      const payload = getPayload();
      const res = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (!data.ok) throw new Error(data.error);

      try {
        sessionStorage.setItem('sentinelpay_last_analysis', JSON.stringify(data.result));
      } catch (e) {}

      const txId = data.result.transaction_id || payload.card_id;
      window.location.href = `/investigation?id=${encodeURIComponent(txId)}`;
    } catch (err) {
      alert('Assessment Error: ' + err.message);
      if (btn) {
        btn.disabled = false;
        btn.textContent = 'Analyze';
      }
    }
  });
}

if (pdfBtn) {
  pdfBtn.addEventListener('click', async () => {
    try {
      const payload = getPayload();
      const res = await fetch('/api/report', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (!res.ok) {
        const d = await res.json();
        throw new Error(d.error);
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'sentinelpay_transaction_report.pdf';
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      alert(e.message);
    }
  });
}
