# This file is part of ContretempsBot <https://github.com/PlaySorbonne/contretemps-bot>
# Copyright (C) 2023-present PLAY SORBONNE UNIVERSITE
# Copyright (C) 2023 DaBlumer
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import traceback
from datetime import datetime

from discord import NotFound
from bot import bot


async def fetch_channel_opt(cid):
    if cid is not None:
      try:
        return bot.get_channel(int(cid))
      except NotFound:
        return None
    return None

async def fetch_message_opt(cid, mid):
    if mid is not None:
        try :
            return await bot.get_channel(int(cid)).fetch_message(int(mid))
        except NotFound:
            return None
    return None

async def fetch_message_list_opt(channel_id, msg_ids, purge=False):
    if msg_ids is None: return None
    l = [await fetch_message_opt(channel_id, msg_id) for msg_id in msg_ids.split(';')]
    if None in l:
        if purge: await purge_opt_message_list(l)
        return None
    return l

async def purge_opt_message_list(l):
    for m in l:
        if m is not None:
            try: await m.delete()
            except Exception : pass

def split_long_message(what):
  MAX_MESSAGE_ALLOWED=1750
  messages = messages.split(';')
  if not what['content'].strip(): what['content']='empty message'
  if len(what['content'])>MAX_MESSAGE_ALLOWED:
    lines = what['content'].strip().split('\n')[::-1]
    good_contents = []
    while lines:
      base = lines.pop()
      if len(base)>MAX_MESSAGE_ALLOWED:
        parts_of_base = [
          base[MAX_MESSAGE_ALLOWED*i:MAX_MESSAGE_ALLOWED*(i+1)]
          +'...' 
          for i in range((len(base)-1)//MAX_MESSAGE_ALLOWED + 1)
        ]
        good_contents += parts_of_base
      else:
        base_string = ""
        while lines and len(base_string) + len(lines[-1]) <= MAX_MESSAGE_ALLOWED:
          base_string += lines.pop()+'\n'
        if base_string.strip(): good_contents.append(base_string)
    return good_contents
  return [what['content']]

async def publish_long_message(messages, channel_id, what):
  old_len_messages = len(messages)
  assert old_len_messages # at least one message ?
  try:
    def next_message(next_id, total, num):
      return (
        f"\n[**Partie {num}/{total}.\n"
       +f"Partie {num+1}/{total}: {next_id}**]"
      )
    def last_message(prec_id, total, num):
      return (
        f"[**Partie {num}/{total}.\n"
       +f"Partie {num-1}/{total}: {prec_id}**]\n\n"
      )
    channel = await fetch_channel_opt(channel_id)
    if len(what['content'])>MAX_MESSAGE_ALLOWED:
      lines = what['content'].strip().split('\n')[::-1]
      good_contents = []
      while lines:
        base = lines.pop()
        if len(base)>MAX_MESSAGE_ALLOWED:
          parts_of_base = [
            base[MAX_MESSAGE_ALLOWED*i:MAX_MESSAGE_ALLOWED*(i+1)]
            +'...' 
            for i in range((len(base)-1)//MAX_MESSAGE_ALLOWED + 1)
          ]
          good_contents += parts_of_base
        else:
          base_string = ""
          while lines and len(base_string) + len(lines[-1]) <= MAX_MESSAGE_ALLOWED:
            base_string += lines.pop()+'\n'
          if base_string.strip(): good_contents.append(base_string)
      n_messages = len(good_contents)
      if n_messages > len(messages):
        for _ in range(n_messages-len(messages)):
          new_message = await channel.send(
            '(Message pour des raisons logistiques) <:'
          )
          messages.append(str(new_message.id))
    else: good_contents, n_messages = [what['content']], 1
    main = await fetch_message_opt(channel_id, messages[0])
    nxt = await fetch_message_opt(channel_id, messages[1]) if len(messages)>=2 else 0
    what['content'] = (
      good_contents[0]
     +(next_message(nxt.jump_url, n_messages, 1) if n_messages >= 2 else "")
    )
    #print(*good_contents, sep='\n\n')
    await main.edit(**what)
    for i in range(1, n_messages):
      msg = await fetch_message_opt(channel_id, messages[i])
      prec = await fetch_message_opt(channel_id, messages[i-1])
      succ = (await fetch_message_opt(channel_id, messages[i+1]) 
        if i<n_messages-1
        else None
      )
      await msg.edit(content=
        last_message(prec.jump_url, n_messages, i+1)
       +good_contents[i]
       +(next_message(succ.jump_url, n_messages, i+1) if i < n_messages-1 else "")
      )
    for k in range(n_messages, len(messages)):
      msg = await fetch_message_opt(channel_id, messages[k])
      assert k > 0, f"publish_long_message(channel_id={channel_id}): 0 message"
      await msg.delete()
    messages = messages[:n_messages]
    return ';'.join(messages)
  except Exception as e:
    print(f"Exception on time {datetime.utcnow()} on publish_long_message")
    print(traceback.format_exc())
    for i in range(old_len_messages, len(messages)):
      #Delete added messages if it does not work
      message = fetch_message_opt(channel_id, messages[i])
      try: await message.delete()
      except Exception: pass
    messages = messages[:old_len_messages]
    for m in messages:
      try: await message.edit("Erreur de publication de message :(", ephemeral=True)
      except Exception: pass
    return ';'.join(messages)

async def publish_long_ephemeral(sender, what):
  good_contents = split_long_message(what)
  for i, content in enumerate(good_contents):
    await sender(content+f" (Partie {i+1}/{len(good_contents)})")
