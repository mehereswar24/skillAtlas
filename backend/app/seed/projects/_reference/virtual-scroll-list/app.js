function renderVisible(container, items, { rowHeight, viewportHeight }) {
  container.innerHTML = '';
  container.style.height = viewportHeight + 'px';
  container.style.overflowY = 'auto';
  container.style.position = 'relative';

  const spacer = document.createElement('div');
  spacer.className = 'spacer';
  spacer.style.height = items.length * rowHeight + 'px';
  container.append(spacer);

  const viewport = document.createElement('div');
  viewport.className = 'viewport';
  viewport.style.position = 'absolute';
  viewport.style.top = '0';
  viewport.style.left = '0';
  viewport.style.right = '0';
  container.append(viewport);

  function update() {
    const visibleCount = Math.ceil(viewportHeight / rowHeight) + 1;
    const maxStart = Math.max(0, items.length - visibleCount);
    const rawStart = Math.floor(container.scrollTop / rowHeight);
    const start = Math.min(Math.max(0, rawStart), maxStart);
    const end = Math.min(items.length, start + visibleCount);

    viewport.style.transform = `translateY(${start * rowHeight}px)`;
    viewport.innerHTML = '';
    for (let i = start; i < end; i++) {
      const row = document.createElement('div');
      row.className = 'row';
      row.style.height = rowHeight + 'px';
      row.textContent = items[i];
      viewport.append(row);
    }
  }

  container.addEventListener('scroll', update);
  update();
}

window.renderVisible = renderVisible;
