function renderRows(container, count) {
  container.textContent = '';

  // Built off-document, so the browser lays out once instead of `count` times.
  const fragment = document.createDocumentFragment();
  for (let i = 1; i <= count; i++) {
    const row = document.createElement('div');
    row.className = 'row';
    row.textContent = 'Row ' + i;
    fragment.append(row);
  }
  container.append(fragment);

  return count;
}

window.renderRows = renderRows;
