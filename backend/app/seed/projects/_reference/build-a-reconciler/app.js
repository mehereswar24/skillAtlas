function h(tag, props, ...children) {
  return { tag, props: props || {}, children: children.flat() };
}

function render(vnode) {
  if (typeof vnode === 'string') return document.createTextNode(vnode);

  const node = document.createElement(vnode.tag);
  for (const [key, value] of Object.entries(vnode.props)) {
    if (key.startsWith('on')) {
      node.addEventListener(key.slice(2).toLowerCase(), value);
    } else {
      node.setAttribute(key, value);
    }
  }
  for (const child of vnode.children) node.append(render(child));
  return node;
}

function changed(a, b) {
  return (
    typeof a !== typeof b ||
    (typeof a === 'string' && a !== b) ||
    a.tag !== b.tag
  );
}

function patch(parent, oldVNode, newVNode, index = 0) {
  if (oldVNode == null) {
    parent.append(render(newVNode));
  } else if (newVNode == null) {
    if (parent.childNodes[index]) parent.removeChild(parent.childNodes[index]);
  } else if (changed(oldVNode, newVNode)) {
    parent.replaceChild(render(newVNode), parent.childNodes[index]);
  } else if (newVNode.tag) {
    const node = parent.childNodes[index];

    for (const [key, value] of Object.entries(newVNode.props)) {
      if (!key.startsWith('on') && oldVNode.props[key] !== value) {
        node.setAttribute(key, value);
      }
    }
    for (const key of Object.keys(oldVNode.props)) {
      if (!key.startsWith('on') && !(key in newVNode.props)) {
        node.removeAttribute(key);
      }
    }

    const length = Math.max(oldVNode.children.length, newVNode.children.length);
    // Backwards, so removing a child does not shift the indices still to visit.
    for (let i = length - 1; i >= 0; i--) {
      patch(node, oldVNode.children[i], newVNode.children[i], i);
    }
  }
}

window.h = h;
window.render = render;
window.patch = patch;
