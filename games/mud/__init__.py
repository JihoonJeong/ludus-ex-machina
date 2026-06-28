"""MUD — text-adventure field (16-bit adventure soul, language world-model).

A room-graph world with stateful objects and deterministic verbs. Single-agent
first (clean world-model eval); the engine is multi-agent-capable for a later
shared-world (MUD) layer. Zones are authored data (games/mud/zones.py); the
engine is a generic verb interpreter over that data.
"""
