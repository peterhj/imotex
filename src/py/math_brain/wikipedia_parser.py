#!/usr/bin/env python3
"""
Does a best-effort parse of a wikipedia article.
"""
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from typing import Dict, List, Optional
import xml.etree.ElementTree as ET

from util.str_util import ellipsize, get_html_header_level
from util.web_cache import WebCache
from util.xml_util import elem_to_str, get_inside_text, get_node


def latexify(tree: ET.Element):
    """
    In wikipedia, when you want to write latex, you write something like:

    <math>x^2 + y^2 = r^2.\!\ </math>

    This renders as if you wrote this in latex:

    $$x^2 + y^2 = r^2.\!\ $$

    The resultant html seems to display as an <img>, with the source latex
    available in the alt= tag of the img element.

    This function accepts an ET.Element, and recursively searches the tree for
    elements that came from <math> source. Such elements are rewritten in
    latex format, and wrapped with artificial <latex>...</latex> tags.
    """
    if tree.tag == 'span' and tree.attrib.get('class', '').startswith('mwe-math-'):
        img = get_node(tree, 'img')
        alt = img.attrib['alt']
        elems = list(tree)
        for elem in elems:
            tree.remove(elem)
        assert len(tree) == 0, elem_to_str(tree)
        latex = ET.SubElement(tree, 'latex')
        latex.text = alt
        return
    for elem in tree:
        latexify(elem)


def is_irrelevant(elem: ET.Element) -> bool:
    if elem.tag == 'p' and elem.attrib.get('class', '') == 'mw-empty-elt':
        return True
    if elem.tag == 'div' and elem.attrib.get('style', '').find('display:none') != -1:
        return True
    if elem.tag == 'div' and not get_inside_text(elem):
        return True
    if elem.tag == 'div' and elem.attrib.get('role', '') == 'note':
        return True
    if elem.tag == 'table' and elem.attrib.get('class', '') == 'infobox':
        return True
    if elem.tag == 'table' and elem.attrib.get('class', '').find('vertical-navbox') != -1:
        return True
    if elem.tag == 'style':
        return True
    if elem.tag == 'div' and elem.attrib.get('class', '').startswith('toc'):
        return True
    if elem.tag == 'div' and elem.attrib.get('class', '').startswith('thumb '):
        return True
    return False


class WikiTree:
    """
    The contents of a wikipedia article are represented as a WikiTree.

    Each header level (<h1>, <h2>, ...) corresponds to a depth-level of the
    tree.

    A WikiTree has a str title, an intro (a possibly-empty list of
    ET.Elements), and branches (a possibly-empty list of WikiTree's of higher
    h-level).

    ET.Elements devoid of relevant content are stripped out.
    """
    def __init__(self, header: ET.Element, body: List[ET.Element]):
        header_level = get_html_header_level(header.tag)
        assert header_level is not None
        if header_level == 1:
            # This is the top-level header, the name of the article
            title = get_inside_text(header)
        else:
            span = get_node(header, 'span', {'class': 'mw-headline'})
            title = get_inside_text(span)

        branches = []

        nodes = [elem for elem in body if not is_irrelevant(elem)]
        n = len(nodes)
        sub_lvls = [get_html_header_level(node.tag) for node in nodes]
        sub_lvls = [lvl for lvl in sub_lvls if lvl is not None]
        intro_bound = n
        if sub_lvls:
            next_lvl = min(sub_lvls)
            assert next_lvl > header_level
            sub_indices = [i for (i, node) in enumerate(nodes) if get_html_header_level(node.tag) == next_lvl]
            intro_bound = sub_indices[0]
            num_sub_indices = len(sub_indices)
            sub_indices.append(len(nodes))  # to make loop cleaner
            for h in range(num_sub_indices):
                sub_index = sub_indices[h]
                next_sub_index = sub_indices[h+1]
                tree = WikiTree(nodes[sub_index], nodes[sub_index+1:next_sub_index])
                if tree.title in ('See also', 'References', 'Further reading', 'External links'):
                    # maybe these could be useful but leaving it out looks prettier for now
                    continue
                branches.append(tree)

        intro = nodes[:intro_bound]

        self._level = header_level
        self._title = title
        self._intro = intro
        self._branches = branches

    @property
    def level(self) -> int:
        return self._level

    @property
    def title(self) -> str:
        return self._title

    @property
    def intro(self) -> List[ET.Element]:
        return self._intro

    @property
    def branches(self) -> List['WikiTree']:
        return self._branches

    def dump(self, column_width: Optional[int]=None):
        indent = '*' * (self.level - 1)
        str_len = None if column_width is None else (column_width - len(indent))
        print(f'{indent}{ellipsize(self.title, str_len)}')
        print('')
        indent = ' ' * self.level
        str_len = None if column_width is None else (column_width - len(indent))
        for elem in self.intro:
            print(f'{indent}{ellipsize(elem_to_str(elem), str_len)}')
            print('')
        for branch in self.branches:
            branch.dump(column_width)


class WikiArticle:
    """
    A structured representation of a wikipedia article.

    The implementation of this class takes advantage of the very specific
    format of each article.
    """
    @staticmethod
    def fix_malformed_html(text):
        """
        The standard wikipedia article contains malformed html. This appears to
        fix the text to something that xml.etree.ElementTree can parse.
        """
        line_hack = (
                '<input type="hidden" name="title" value="Special:Search">',
                '<input type="hidden" name="title" value="Special:Search"/>'
                )
        return text.replace(line_hack[0], line_hack[1])

    def __init__(self, text: str):
        self.sections: List[WikiSection] = []

        tree = ET.fromstring(WikiArticle.fix_malformed_html(text))
        latexify(tree)
        body = tree.find('body')
        content = get_node(body, 'div', {'id': 'content'})
        h1 = get_node(content, 'h1')
        body_content = get_node(content, 'div', {'id': 'bodyContent'})
        mw_content_text = get_node(body_content, 'div', {'id': 'mw-content-text'})
        mw_parser_output = get_node(mw_content_text, 'div', {'class': 'mw-parser-output'})

        # mw_parser_output is the meat of the article. Segment into sections by
        # looking for h2 tags
        nodes = list(mw_parser_output)
        self._root = WikiTree(h1, nodes)

    @property
    def root(self) -> WikiTree:
        return self._root

    def dump(self, column_width: Optional[int]=None):
        self.root.dump(column_width)


class WikipediaParser:
    def __init__(self, cache: Optional[WebCache]=None):
        self._cache = cache
        if cache is None:
            self._cache = WebCache()

    def parse(self, url) -> WikiArticle:
        """
        Example url: https://en.wikipedia.org/wiki/Circle
        """
        text = self._cache.html_request(url)
        return WikiArticle(text)


def main():
    if len(sys.argv) != 2:
        script = os.path.basename(__file__)
        print(f'Usage: {script} <TOPIC>')
        print(f'Example: {script} circle')
        pass

    topic = sys.argv[1].lower()
    parser = WikipediaParser()
    if not topic.startswith('http'):
        url = f'https://en.wikipedia.org/wiki/{topic}'
    else:
        url = topic
    parser.parse(url).dump()


if __name__ == '__main__':
    main()

