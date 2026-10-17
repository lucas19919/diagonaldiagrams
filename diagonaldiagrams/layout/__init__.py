"""Layout kernels (DESIGN 7): where things go. A layout never paints.

layered.layout() places boxes in layers and routes the arrows between them (flow, arch, schema);
sequence.layout() places actors and messages (seq). The renderers in diagrams.py call them.
"""
