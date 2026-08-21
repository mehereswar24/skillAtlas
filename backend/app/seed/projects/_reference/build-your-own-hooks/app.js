function createHooksRuntime() {
  const slots = [];
  let index = 0;
  let currentComponent = null;

  function useState(initial) {
    const i = index++;
    if (i >= slots.length) slots[i] = initial;

    const setState = (next) => {
      slots[i] = typeof next === 'function' ? next(slots[i]) : next;
      run();
    };
    return [slots[i], setState];
  }

  function run() {
    index = 0;
    return currentComponent();
  }

  function render(component) {
    currentComponent = component;
    return run();
  }

  return { useState, render };
}

window.createHooksRuntime = createHooksRuntime;
