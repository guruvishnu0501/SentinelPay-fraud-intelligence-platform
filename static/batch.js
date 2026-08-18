const file = document.getElementById('csvFile');
const btn = document.getElementById('analyzeBtn');
const out = document.getElementById('batchResult');

function esc(val) {
  const str = val == null ? '' : String(val);
  return str.replace(/[&<>"']/g, m => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[m]));
}

let batchCurrentPage = 1;
const batchPageSize = 10;

function applyBatchFilters() {
  const merchantSel = document.getElementById('filterMerchant');
  const decisionSel = document.getElementById('filterDecision');
  const tierSel = document.getElementById('filterTier');
  const countSpan = document.getElementById('filteredCount');
  const tbody = document.getElementById('batchTbody');
  const prevBtn = document.getElementById('batchPrevPage');
  const nextBtn = document.getElementById('batchNextPage');
  const pageInfo = document.getElementById('batchPageInfo');

  if (!tbody) return;

  const selectedMerchant = merchantSel ? merchantSel.value : 'ALL';
  const selectedDecision = decisionSel ? decisionSel.value : 'ALL';
  const selectedTier = tierSel ? tierSel.value : 'ALL';

  const filtered = allBatchRows.filter(r => {
    if (selectedMerchant !== 'ALL' && String(r.merchant_name) !== selectedMerchant) return false;
    if (selectedDecision !== 'ALL' && String(r.decision) !== selectedDecision) return false;
    if (selectedTier !== 'ALL' && String(r.risk_level) !== selectedTier) return false;
    return true;
  });

  const totalItems = filtered.length;
  const totalPages = Math.max(1, Math.ceil(totalItems / batchPageSize));

  if (batchCurrentPage > totalPages) batchCurrentPage = totalPages;
  if (batchCurrentPage < 1) batchCurrentPage = 1;

  if (countSpan) {
    countSpan.textContent = `Showing ${totalItems} of ${allBatchRows.length} transactions`;
  }

  if (pageInfo) {
    pageInfo.textContent = `Page ${batchCurrentPage} of ${totalPages} (10 per page)`;
  }

  if (prevBtn) prevBtn.disabled = batchCurrentPage <= 1;
  if (nextBtn) nextBtn.disabled = batchCurrentPage >= totalPages;

  if (!totalItems) {
    tbody.innerHTML = `<tr><td colspan="9" class="empty-state">No transactions match the selected filter combination.</td></tr>`;
    return;
  }

  const startIndex = (batchCurrentPage - 1) * batchPageSize;
  const preview = filtered.slice(startIndex, startIndex + batchPageSize);

  tbody.innerHTML = preview.map(r => {
    const dec = r && r.decision != null ? String(r.decision) : 'N/A';
    const tier = r && r.risk_level != null ? String(r.risk_level) : 'N/A';
    const score = r && r.operational_risk_score != null ? r.operational_risk_score : 'N/A';
    const action = r && r.recommended_action != null ? String(r.recommended_action) : 'N/A';
    const reasons = r && r.reasons != null ? String(r.reasons) : '';
    const cardId = r && r.card_id != null ? String(r.card_id) : '';
    const timeStr = r && r.trans_date_trans_time != null ? String(r.trans_date_trans_time) : '';
    const amount = r && r.amount_inr != null ? r.amount_inr : '';
    const merchant = r && r.merchant_name != null ? String(r.merchant_name) : '';

    let badgeClass = 'low';
    if (dec === 'SUSPICIOUS TRANSACTION') badgeClass = 'medium';
    if (dec === 'FRAUDULENT TRANSACTION' || dec === 'INPUT ERROR') badgeClass = 'high';

    return `
      <tr>
        <td><b>${esc(cardId)}</b></td>
        <td>${esc(timeStr)}</td>
        <td>₹${esc(Number(amount).toLocaleString())}</td>
        <td>${esc(merchant)}</td>
        <td><b>${esc(dec)}</b></td>
        <td><span class="badge-risk ${badgeClass}">${esc(tier)}</span></td>
        <td><b>${esc(score)}</b></td>
        <td>${esc(action)}</td>
        <td style="max-width: 280px; font-size: 12px; color: var(--text-muted);">${esc(reasons)}</td>
      </tr>
    `;
  }).join('');
}

if (btn) {
  btn.addEventListener('click', async () => {
    if (!file.files.length) {
      alert('Select a CSV file first.');
      return;
    }

    out.classList.remove('hidden');
    out.innerHTML = '<div class="empty-state">Screening batch dataset chronologically through SentinelPay Risk Engine…</div>';

    const fd = new FormData();
    fd.append('file', file.files[0]);

    try {
      const res = await fetch('/api/batch', { method: 'POST', body: fd });
      const data = await res.json();

      if (!data || !data.ok) {
        const err = data && data.error != null ? String(data.error) : 'Batch analysis failed.';
        throw new Error(err);
      }

      const summary = data.summary || {};
      allBatchRows = data.rows || [];
      const rawCsv = data.csv != null ? String(data.csv) : '';

      const totalRows = summary.total_rows != null ? summary.total_rows : allBatchRows.length;
      const genuineCount = summary.genuine_count != null ? summary.genuine_count : 0;
      const suspiciousCount = summary.suspicious_count != null ? summary.suspicious_count : 0;
      const fraudCount = summary.fraud_count != null ? summary.fraud_count : 0;
      const errorCount = summary.error_count != null ? summary.error_count : 0;
      const avgScore = summary.avg_risk_score != null ? summary.avg_risk_score : 'N/A';

      localStorage.removeItem('sentinelpay_session_cleared');

      const merchantsList = Array.from(new Set(allBatchRows.map(r => r.merchant_name).filter(Boolean))).sort();

      out.innerHTML = `
        <div class="section-title">Screening Summary</div>
        <div class="kpi-grid" style="margin-bottom: 20px;">
          <div class="kpi-card">
            <div class="label">Total Transactions</div>
            <div class="value">${esc(totalRows)}</div>
          </div>
          <div class="kpi-card">
            <div class="label">Low Risk</div>
            <div class="value low">${esc(genuineCount)}</div>
          </div>
          <div class="kpi-card">
            <div class="label">Medium Risk</div>
            <div class="value med">${esc(suspiciousCount)}</div>
          </div>
          <div class="kpi-card">
            <div class="label">High Risk</div>
            <div class="value high">${esc(fraudCount)}</div>
          </div>
          <div class="kpi-card">
            <div class="label">Input Errors</div>
            <div class="value" style="color: var(--text-dim);">${esc(errorCount)}</div>
          </div>
          <div class="kpi-card">
            <div class="label">Average Risk Score</div>
            <div class="value">${esc(avgScore)} <span style="font-size: 14px; color: var(--text-muted);">/ 100</span></div>
          </div>
        </div>

        <div class="panel" style="background: var(--bg-card); padding: 16px; margin-bottom: 20px;">
          <div class="form-grid" style="grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 12px;">
            <div class="field-group">
              <label>Merchant Filter</label>
              <select id="filterMerchant">
                <option value="ALL">All Merchants (${merchantsList.length})</option>
                ${merchantsList.map(m => `<option value="${esc(m)}">${esc(m)}</option>`).join('')}
              </select>
            </div>
            <div class="field-group">
              <label>Decision Filter</label>
              <select id="filterDecision">
                <option value="ALL">All Decisions</option>
                <option value="GENUINE TRANSACTION">Genuine Transaction</option>
                <option value="SUSPICIOUS TRANSACTION">Suspicious Transaction</option>
                <option value="FRAUDULENT TRANSACTION">Fraudulent Transaction</option>
              </select>
            </div>
            <div class="field-group">
              <label>Risk Tier Filter</label>
              <select id="filterTier">
                <option value="ALL">All Risk Tiers</option>
                <option value="LOW">LOW</option>
                <option value="MEDIUM">MEDIUM</option>
                <option value="HIGH">HIGH</option>
              </select>
            </div>
          </div>

          <div style="display: flex; justify-content: space-between; align-items: center;">
            <span id="filteredCount" style="font-size: 13px; font-weight: 600; color: var(--accent);">Showing ${totalRows} of ${totalRows} transactions</span>
            <button id="downloadBtn" class="btn btn-primary">Download Predictions CSV</button>
          </div>
        </div>

        <div class="table-container">
          <table>
            <thead>
              <tr>
                <th>Card ID</th>
                <th>Date / Time</th>
                <th>Amount (₹)</th>
                <th>Merchant</th>
                <th>Decision</th>
                <th>Risk Tier</th>
                <th>Risk Score</th>
                <th>Action</th>
                <th>Reasons</th>
              </tr>
            </thead>
            <tbody id="batchTbody"></tbody>
          </table>
        </div>

        <!-- Pagination Controls -->
        <div id="batchPagination" style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; margin-top: 16px; background: var(--bg-card); padding: 12px 16px; border-radius: 8px; border: 1px solid var(--border);">
          <button id="batchPrevPage" class="btn btn-secondary" style="font-size: 12px; padding: 6px 14px;" disabled>← Previous Page</button>
          <span id="batchPageInfo" style="font-size: 13px; font-weight: 600; color: var(--accent);">Page 1 of 1 (10 per page)</span>
          <button id="batchNextPage" class="btn btn-primary" style="font-size: 12px; padding: 6px 14px;">Like to know more? Click Next Page →</button>
        </div>
      `;

      batchCurrentPage = 1;
      applyBatchFilters();

      ['filterMerchant', 'filterDecision', 'filterTier'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.addEventListener('change', () => {
          batchCurrentPage = 1;
          applyBatchFilters();
        });
      });

      const prevBtn = document.getElementById('batchPrevPage');
      if (prevBtn) {
        prevBtn.onclick = () => {
          if (batchCurrentPage > 1) {
            batchCurrentPage--;
            applyBatchFilters();
          }
        };
      }

      const nextBtn = document.getElementById('batchNextPage');
      if (nextBtn) {
        nextBtn.onclick = () => {
          batchCurrentPage++;
          applyBatchFilters();
        };
      }

      const dlBtn = document.getElementById('downloadBtn');
      if (dlBtn) {
        dlBtn.onclick = () => {
          if (!rawCsv) {
            alert('No CSV content available to download.');
            return;
          }
          const blob = new Blob([rawCsv], { type: 'text/csv;charset=utf-8;' });
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = 'sentinelpay_batch_predictions.csv';
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
          URL.revokeObjectURL(url);
        };
      }
    } catch (e) {
      const msg = e && e.message != null ? String(e.message) : 'Unknown batch error occurred.';
      out.innerHTML = `<div class="reason-item" style="border-color: var(--high-red);"><p><b>Batch Processing Error:</b> ${esc(msg)}</p></div>`;
    }
  });
}
