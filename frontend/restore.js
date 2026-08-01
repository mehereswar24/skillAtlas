const fs = require('fs');
const readline = require('readline');

async function restore() {
  const logFile = 'C:\\Users\\Mehereswar\\.gemini\\antigravity-cli\\brain\\5bed61f0-9243-47cd-98c0-bcaf05e28dcd\\.system_generated\\logs\\transcript_full.jsonl';
  const fileStream = fs.createReadStream(logFile);
  const rl = readline.createInterface({
    input: fileStream,
    crlfDelay: Infinity
  });

  let targetContent = null;

  for await (const line of rl) {
    if (!line) continue;
    try {
      const step = JSON.parse(line);
      // look for view_file
      if (step.type === 'TOOL_RESPONSE' && step.content) {
        if (step.content.includes('landing-page-interactive.tsx') && step.content.includes('Total Lines')) {
          targetContent = step.content;
          console.log("FOUND ONE with length", step.content.length);
        }
      }
    } catch (e) {}
  }

  if (targetContent) {
    // Extract the lines
    const lines = targetContent.split('\n');
    const cleanedLines = [];
    for (const l of lines) {
      if (l.match(/^\d+:\s/)) {
        cleanedLines.push(l.replace(/^\d+:\s/, ''));
      }
    }
    
    fs.writeFileSync('C:\\Users\\Mehereswar\\learn-nexus\\frontend\\src\\components\\landing-page-interactive.tsx', cleanedLines.join('\n'));
    console.log('Restored successfully');
  } else {
    console.log('Not found');
  }
}

restore();
