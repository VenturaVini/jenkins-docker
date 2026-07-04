// Gerado pelo deploy.sh — não edite o workflow no n8n, edite este template e rode o deploy de novo.
const CFG = __CONFIG_JSON__;

const TG = `https://api.telegram.org/bot${CFG.botToken}`;
const INSTANCES = CFG.instances.map((i) => ({
  ...i,
  auth: 'Basic ' + Buffer.from(`${i.user}:${i.token}`).toString('base64'),
}));
const MULTI = INSTANCES.length > 1;
const ALLOWED_CHAT_IDS = CFG.allowedChats || [];

const http = this.helpers.httpRequest.bind(this);

async function tg(method, body) {
  return http({ method: 'POST', url: `${TG}/${method}`, body, json: true });
}

async function jenkins(inst, path, method = 'GET', raw = false) {
  return http({
    method,
    url: `${inst.url}${path}`,
    headers: { Authorization: inst.auth },
    json: !raw,
    returnFullResponse: method === 'POST',
  });
}

const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const jobLabel = (inst, job) => (MULTI ? `${inst.name} · ${job}` : job);

function colorEmoji(color) {
  if (!color) return '⚪';
  if (color.includes('anime')) return '🔄';
  if (color.startsWith('blue')) return '✅';
  if (color.startsWith('red')) return '❌';
  if (color.startsWith('yellow')) return '⚠️';
  if (color.startsWith('disabled')) return '⏸️';
  return '⚪';
}

const resultEmoji = (r) => (r === 'SUCCESS' ? '✅' : r === 'FAILURE' ? '❌' : r === 'ABORTED' ? '🛑' : '⚠️');
const when = (ts) => new Date(ts).toLocaleString('pt-BR', { timeZone: 'America/Sao_Paulo' });
const fmtDur = (ms) => (ms >= 60000 ? `${Math.floor(ms / 60000)}m${Math.round((ms % 60000) / 1000)}s` : `${Math.round(ms / 1000)}s`);

const HELP = `<b>🤖 Jenkins Bot — comandos</b>

/jobs — lista os jobs com botões (toque, sem digitar)
/run <code>job</code> — dispara um build (aviso quando terminar)
/run <code>job PARAM=valor</code> — build com parâmetros
/status <code>job</code> — detalhes do último build
/log <code>job</code> — últimas linhas do console
/stop <code>job</code> — aborta o build em execução
/queue — fila de builds aguardando
/watch — liga/desliga avisos de todo build que terminar
/jenkins — status das instâncias Jenkins
/chatid — id deste chat
/help — esta mensagem`;

// Resolve em qual instância o job existe (quando o usuário digita só o nome).
async function findInstance(job) {
  for (const inst of INSTANCES) {
    try {
      await jenkins(inst, `/job/${encodeURIComponent(job)}/api/json?tree=name`);
      return inst;
    } catch (e) { /* não está nesta instância */ }
  }
  return null;
}

async function logTail(inst, job, lines = 25) {
  const txt = await jenkins(inst, `/job/${encodeURIComponent(job)}/lastBuild/consoleText`, 'GET', true);
  const all = String(txt).trimEnd().split('\n');
  let tail = all.slice(-lines).join('\n');
  if (tail.length > 3200) tail = tail.slice(-3200);
  return tail;
}

async function handleCommand(cmd, args, chatId, sd) {
  // Callbacks dos botões vêm como "cmd <idx-da-instância> <job>"; texto digitado vem como "cmd <job>".
  let inst = null;
  if (/^\d+$/.test(args[0] || '') && INSTANCES[+args[0]]) {
    inst = INSTANCES[+args[0]];
    args = args.slice(1);
  }
  const job = args[0];
  const params = args.slice(1).filter((a) => a.includes('='));
  const needsJob = ['/run', '/status', '/log', '/stop'].includes(cmd);
  if (needsJob) {
    if (!job) return { text: `Informe o job. Ex.: ${cmd} robo-scraper` };
    if (!inst) inst = await findInstance(job);
    if (!inst) return { text: `❌ Job <code>${esc(job)}</code> não encontrado em nenhuma instância. Use /jobs.` };
  }
  const idx = inst ? INSTANCES.indexOf(inst) : 0;
  const key = inst ? `${idx}:${job}` : null;

  if (cmd === '/jobs') {
    const sections = [];
    const keyboard = [];
    for (let i = 0; i < INSTANCES.length; i++) {
      const it = INSTANCES[i];
      try {
        const data = await jenkins(it, '/api/json?tree=jobs[name,color]');
        if (MULTI) sections.push(`<b>🏭 ${esc(it.name)}</b> — ${data.jobs.length} jobs`);
        for (const j of data.jobs) {
          keyboard.push([
            { text: `${colorEmoji(j.color)} ${jobLabel(it, j.name)}`, callback_data: `status ${i} ${j.name}` },
            { text: '▶️ rodar', callback_data: `run ${i} ${j.name}` },
            { text: '📜 log', callback_data: `log ${i} ${j.name}` },
          ]);
        }
      } catch (e) {
        sections.push(`❌ <b>${esc(it.name)}</b> fora do ar (${esc(it.url)})`);
      }
    }
    if (!keyboard.length && !sections.length) return { text: 'Nenhum job encontrado.' };
    return {
      text: `<b>📋 Jobs do Jenkins</b>\n${sections.join('\n')}\nToque em um botão para agir:`,
      reply_markup: { inline_keyboard: keyboard },
    };
  }

  if (cmd === '/run') {
    let last = { number: 0 };
    try {
      last = await jenkins(inst, `/job/${encodeURIComponent(job)}/lastBuild/api/json?tree=number`);
    } catch (e) { /* job nunca buildado */ }
    if (params.length) {
      const qs = params.map((p) => p.split('=').map(encodeURIComponent).join('=')).join('&');
      await jenkins(inst, `/job/${encodeURIComponent(job)}/buildWithParameters?${qs}`, 'POST');
    } else {
      await jenkins(inst, `/job/${encodeURIComponent(job)}/build`, 'POST');
    }
    sd.pendingRuns[key] = [...new Set([...(sd.pendingRuns[key] || []), chatId])];
    if (sd.lastSeen[key] === undefined) sd.lastSeen[key] = last.number || 0;
    const p = params.length ? `\nParâmetros: <code>${esc(params.join(' '))}</code>` : '';
    return { text: `🚀 Build de <code>${esc(jobLabel(inst, job))}</code> disparado!${p}\nAviso aqui quando terminar.` };
  }

  if (cmd === '/status') {
    const b = await jenkins(inst, `/job/${encodeURIComponent(job)}/lastBuild/api/json?tree=number,result,building,timestamp,duration,estimatedDuration`);
    let state, dur;
    if (b.building) {
      const elapsed = Date.now() - b.timestamp;
      const pct = b.estimatedDuration > 0 ? Math.min(99, Math.round((elapsed / b.estimatedDuration) * 100)) : null;
      state = `🔄 EM EXECUÇÃO${pct !== null ? ` (~${pct}%)` : ''}`;
      dur = `${fmtDur(elapsed)} decorridos`;
    } else {
      state = `${resultEmoji(b.result)} ${b.result}`;
      dur = fmtDur(b.duration);
    }
    return {
      text: `<b>📊 ${esc(jobLabel(inst, job))}</b>\n\nBuild: #${b.number}\nStatus: ${state}\nInício: ${when(b.timestamp)}\nDuração: ${dur}`,
      reply_markup: {
        inline_keyboard: [[
          { text: '▶️ rodar de novo', callback_data: `run ${idx} ${job}` },
          { text: '📜 log', callback_data: `log ${idx} ${job}` },
          ...(b.building ? [{ text: '🛑 abortar', callback_data: `stop ${idx} ${job}` }] : []),
        ]],
      },
    };
  }

  if (cmd === '/log') {
    const tail = await logTail(inst, job, 25);
    return { text: `<b>📜 ${esc(jobLabel(inst, job))} — fim do console</b>\n<pre>${esc(tail)}</pre>` };
  }

  if (cmd === '/stop') {
    const b = await jenkins(inst, `/job/${encodeURIComponent(job)}/lastBuild/api/json?tree=number,building`);
    if (!b.building) return { text: `<code>${esc(job)}</code> não está em execução.` };
    await jenkins(inst, `/job/${encodeURIComponent(job)}/${b.number}/stop`, 'POST');
    return { text: `🛑 Build #${b.number} de <code>${esc(jobLabel(inst, job))}</code> abortado.` };
  }

  if (cmd === '/queue') {
    const out = [];
    for (const it of INSTANCES) {
      try {
        const q = await jenkins(it, '/queue/api/json?tree=items[task[name],why,inQueueSince]');
        for (const i of q.items || []) {
          out.push(`⏳ <code>${esc(jobLabel(it, i.task.name))}</code> — na fila há ${fmtDur(Date.now() - i.inQueueSince)}\n   <i>${esc(i.why || '')}</i>`);
        }
      } catch (e) {
        out.push(`❌ <b>${esc(it.name)}</b> fora do ar`);
      }
    }
    if (!out.length) return { text: '✅ Fila vazia — nenhum build aguardando.' };
    return { text: `<b>⏳ Fila do Jenkins</b>\n\n${out.join('\n')}` };
  }

  if (cmd === '/jenkins') {
    const lines = [];
    for (const it of INSTANCES) {
      try {
        const info = await jenkins(it, '/api/json?tree=numExecutors,jobs[name]');
        lines.push(`✅ <b>${esc(it.name)}</b> — ${info.jobs.length} jobs, ${info.numExecutors} executores\n   <code>${esc(it.url)}</code>`);
      } catch (e) {
        lines.push(`❌ <b>${esc(it.name)}</b> — FORA DO AR\n   <code>${esc(it.url)}</code>`);
      }
    }
    return { text: `<b>🏭 Instâncias Jenkins</b>\n\n${lines.join('\n')}` };
  }

  if (cmd === '/watch') {
    const on = sd.watchChats.includes(chatId);
    if (on) {
      sd.watchChats = sd.watchChats.filter((c) => c !== chatId);
      return { text: '🔕 Watch DESLIGADO — não aviso mais sobre builds neste chat.' };
    }
    sd.watchChats.push(chatId);
    return { text: '🔔 Watch LIGADO — vou avisar aqui sempre que qualquer build terminar.' };
  }

  if (cmd === '/chatid') return { text: `Chat id: <code>${chatId}</code>` };

  return { text: HELP };
}

// ---------- ciclo principal ----------
const sd = $getWorkflowStaticData('global');
sd.lastSeen = sd.lastSeen || {};
sd.pendingRuns = sd.pendingRuns || {};
sd.watchChats = sd.watchChats || [];

const updates = await http({
  url: `${TG}/getUpdates`,
  qs: { offset: sd.tgOffset || 0, timeout: 15, allowed_updates: JSON.stringify(['message', 'callback_query']) },
  json: true,
  timeout: 25000,
});

const handled = [];
for (const u of updates.result || []) {
  sd.tgOffset = u.update_id + 1;

  let text = null;
  let chatId = null;

  if (u.callback_query) {
    chatId = u.callback_query.message?.chat?.id;
    text = '/' + u.callback_query.data;
    tg('answerCallbackQuery', { callback_query_id: u.callback_query.id }).catch(() => {});
  } else if (u.message && u.message.text && u.message.text.startsWith('/')) {
    chatId = u.message.chat.id;
    text = u.message.text;
  }
  if (!text || chatId == null) continue;
  if (ALLOWED_CHAT_IDS.length && !ALLOWED_CHAT_IDS.includes(chatId)) continue;

  const [rawCmd, ...args] = text.trim().split(/\s+/);
  let cmd = rawCmd.split('@')[0].toLowerCase();
  if (cmd === '/start') cmd = '/help';

  let reply;
  try {
    reply = await handleCommand(cmd, args, chatId, sd);
  } catch (err) {
    const notFound = err.message && (err.message.includes('404') || err.message.includes('Not Found'));
    reply = {
      text: notFound
        ? `❌ Job <code>${esc(args[0] || '?')}</code> não encontrado (ou nunca executado). Use /jobs.`
        : `❌ Erro: ${esc(err.message)}`,
    };
  }

  let msgText = reply.text;
  if (msgText.length > 4000) msgText = msgText.slice(0, 3990) + '…';
  await tg('sendMessage', { chat_id: chatId, text: msgText, parse_mode: 'HTML', reply_markup: reply.reply_markup });
  handled.push({ chatId, cmd });
}

// ---------- monitor de builds (watch + avisos de /run) ----------
const notified = [];
const needMonitor = sd.watchChats.length || Object.keys(sd.pendingRuns).length;
if (needMonitor) {
  for (let i = 0; i < INSTANCES.length; i++) {
    const inst = INSTANCES[i];
    let data;
    try {
      data = await jenkins(inst, '/api/json?tree=jobs[name,lastBuild[number,result,building,duration]]');
    } catch (e) {
      continue; // instância fora do ar: tenta no próximo ciclo
    }
    for (const j of data.jobs || []) {
      const lb = j.lastBuild;
      if (!lb) continue;
      const key = `${i}:${j.name}`;
      const seen = sd.lastSeen[key];
      if (seen === undefined) {
        sd.lastSeen[key] = lb.building ? lb.number - 1 : lb.number;
        continue;
      }
      if (!lb.building && lb.number > seen) {
        sd.lastSeen[key] = lb.number;
        const chats = [...new Set([...sd.watchChats, ...(sd.pendingRuns[key] || [])])];
        delete sd.pendingRuns[key];
        if (!chats.length) continue;
        let text = `${resultEmoji(lb.result)} <b>${esc(jobLabel(inst, j.name))}</b> #${lb.number} terminou: <b>${lb.result}</b> em ${fmtDur(lb.duration)}`;
        if (lb.result !== 'SUCCESS') {
          try {
            const tail = await logTail(inst, j.name, 12);
            text += `\n<pre>${esc(tail)}</pre>`;
          } catch (e) { /* sem log */ }
        }
        if (text.length > 4000) text = text.slice(0, 3990) + '…';
        for (const c of chats) {
          await tg('sendMessage', {
            chat_id: c,
            text,
            parse_mode: 'HTML',
            reply_markup: { inline_keyboard: [[{ text: '▶️ rodar de novo', callback_data: `run ${i} ${j.name}` }, { text: '📜 log completo', callback_data: `log ${i} ${j.name}` }]] },
          });
          notified.push({ chat: c, job: j.name, build: lb.number });
        }
      }
    }
  }
}

return [{ json: { updates: (updates.result || []).length, handled, notified } }];
