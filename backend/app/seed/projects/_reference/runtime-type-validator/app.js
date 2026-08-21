function check(schema, value, path = '') {
  const errors = [];
  const prefix = path === '' ? '' : `${path}: `;

  if (typeof schema === 'string') {
    if (typeof value !== schema) {
      errors.push(`${prefix}expected ${schema}, got ${typeof value}`);
    }
    return { valid: errors.length === 0, errors };
  }

  if (schema.type === 'array') {
    if (!Array.isArray(value)) {
      errors.push(`${prefix}expected array, got ${typeof value}`);
      return { valid: false, errors };
    }
    value.forEach((item, index) => {
      errors.push(...check(schema.items, item, `${path}[${index}]`).errors);
    });
    return { valid: errors.length === 0, errors };
  }

  if (schema.type === 'object') {
    if (typeof value !== 'object' || value === null || Array.isArray(value)) {
      errors.push(`${prefix}expected object, got ${typeof value}`);
      return { valid: false, errors };
    }
    const required = schema.required || [];
    for (const key of Object.keys(schema.properties)) {
      const childPath = path ? `${path}.${key}` : key;
      if (value[key] === undefined) {
        if (required.includes(key)) errors.push(`${childPath}: missing required property`);
        continue;
      }
      errors.push(...check(schema.properties[key], value[key], childPath).errors);
    }
    return { valid: errors.length === 0, errors };
  }

  throw new Error(`unknown schema: ${JSON.stringify(schema)}`);
}

window.check = check;
