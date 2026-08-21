function* range(start, end) {
  for (let i = start; i < end; i++) yield i;
}

function* mapIter(iterable, fn) {
  for (const value of iterable) yield fn(value);
}

function* filterIter(iterable, fn) {
  for (const value of iterable) if (fn(value)) yield value;
}

function* takeIter(iterable, n) {
  if (n <= 0) return;
  let count = 0;
  for (const value of iterable) {
    yield value;
    if (++count >= n) return;
  }
}

window.range = range;
window.mapIter = mapIter;
window.filterIter = filterIter;
window.takeIter = takeIter;
