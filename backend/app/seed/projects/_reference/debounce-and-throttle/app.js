function debounce(fn, wait, clock = window) {
  let timer = null;
  return function (...args) {
    if (timer !== null) clock.clearTimeout(timer);
    timer = clock.setTimeout(() => {
      timer = null;
      fn.apply(this, args);
    }, wait);
  };
}

function throttle(fn, wait, clock = window) {
  let cooling = false;
  return function (...args) {
    if (cooling) return;
    fn.apply(this, args);
    cooling = true;
    clock.setTimeout(() => {
      cooling = false;
    }, wait);
  };
}

window.debounce = debounce;
window.throttle = throttle;
