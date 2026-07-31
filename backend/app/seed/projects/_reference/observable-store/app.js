function createStore(initialState) {
  let state = initialState;
  const listeners = new Set();

  function notify() {
    // Iterate a copy: a listener may unsubscribe itself, and mutating the Set
    // mid-iteration would skip whoever came next.
    for (const listener of [...listeners]) listener(state);
  }

  const store = {
    getState() {
      return state;
    },

    setState(updater) {
      const partial = typeof updater === 'function' ? updater(state) : updater;
      // A new object every time, which is what makes Object.is comparison work.
      state = { ...state, ...partial };
      notify();
    },

    subscribe(listener) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },

    select(selector, listener) {
      let previous = selector(state);
      return store.subscribe((next) => {
        const current = selector(next);
        if (!Object.is(previous, current)) {
          previous = current;
          listener(current);
        }
      });
    },
  };

  return store;
}

window.createStore = createStore;
