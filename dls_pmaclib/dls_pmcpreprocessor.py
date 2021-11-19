import os
import re
from logging import getLogger

log = getLogger("dls_pmaclib")


class ClsPmacParser:
    """
    A class that pre-processes Delta-Tau 'pmc' files by making macro
    substitutions and expanding included files (and nested include
    files as deep as necessary).  It may optionally
    strip comments and insert simulation debug information.
    """

    def __init__(self, includePaths=None):
        """
        Create an instance of the preprocessor.  Specify the paths
        to search for include files using the 'includePaths' parameter
        which should be a list of strings, each one specifying a
        path (the current directory is automatically included in
        the search).
        """
        self.fPtr = None
        self.oPtr = None
        self.output = []
        self.includePaths = ["/"]
        if includePaths:
            self.includePaths.extend(includePaths)

        # A couple of regular expressions for use in parsing the pmc file
        self.blankLine = re.compile(r"^\s*$")  # match blank lines
        self.defineLine = re.compile(r"^#(define|DEFINE)\b")  # match macro define-lines
        self.getDefine = re.compile(r"(?<=define\b|DEFINE\b).*$")
        self.splitDefine = re.compile(r"[ \t]+")
        self.includeLine = re.compile(r"^#(include|INCLUDE)\b")  # match include-lines
        self.getInclude = re.compile(r"(?<=include\b|INCLUDE\b).*$")
        self.getCommand = re.compile(
            r"^.*(?=;)|^.*$"
        )  # find command in a line and ignore any comments

    def parse(self, pmcFileName, defines=None, comments=False, debug=False):
        """
        Expand a 'pmc' file.  The 'pmcFileName' is opened and processed
        into expanded text which is returned.  An map of predefined macro
        expansions may be passed ('defines'), along with the booleans
        'comments' and 'debug' which control the stripping of comments and
        the insertion of simulation debug information respectively.
        """
        if defines is None:
            defines = {}

        try:
            self.fPtr = open(pmcFileName, "r")
        except OSError:
            log.error("Error: could not open file: %s" % pmcFileName)
            return None

        self.includePaths.insert(0, os.path.dirname(os.path.abspath(pmcFileName)))

        lineNumber = 0
        for inLine in self.fPtr:
            # Plant simulation debug information
            lineNumber += 1
            if debug:
                self.output.append(
                    ";#* %s %s" % (os.path.abspath(pmcFileName), lineNumber)
                )

            # for annoyingChar in ['\r','\n','\t']:
            # inLine = inLine.strip(annoyingChar)		# remove annoying white
            # space characters
            if not comments:
                inLine = inLine.split(";")[0]  # remove comments

            if self.blankLine.match(inLine):
                self.output.append("")
                continue

            # Match and substitute lines with #define statements in
            if self.defineLine.match(inLine):
                self.output.append("")
                for defineStatement in self.getDefine.findall(inLine):
                    defineStatement = defineStatement.strip()
                    defines.update(
                        {
                            self.splitDefine.split(defineStatement, 1)[
                                0
                            ]: self.substitute_macros(
                                defines, self.splitDefine.split(defineStatement, 1)[1]
                            )
                        }
                    )
                continue

            # Match and substitute #include statements
            if self.includeLine.match(inLine):
                foundFileInPaths = False
                for includeFile in self.getInclude.findall(inLine):
                    includeFile = includeFile.strip(' "\r')
                    for path in self.includePaths:
                        foundFileInPaths = False
                        tmpFullFileName = "%s/%s" % (path, includeFile)
                        if os.path.lexists(tmpFullFileName):
                            includeFile = tmpFullFileName
                            foundFileInPaths = True
                            log.debug("Found file in path: %s", path)
                            break
                    if not foundFileInPaths:
                        log.warning(
                            ";WARNING: Could not find include file: %s",
                            repr(includeFile),
                        )
                        self.output.append("")
                        continue

                    log.info(";Parsing include file: %s" % includeFile)
                    p = ClsPmacParser(self.includePaths)
                    includeLines = p.parse(
                        includeFile, defines=defines, comments=comments, debug=debug
                    )
                    if includeLines:
                        self.output.extend(includeLines)
                    else:
                        self.output.append("")
                continue

            inLine = self.substitute_macros(defines, inLine)
            for annoyingChar in ["\r", "\n", "\t", "\r\n"]:
                if comments:
                    inLine = inLine.rstrip(
                        annoyingChar
                    )  # remove annoying white space characters
                else:
                    inLine = inLine.strip(
                        annoyingChar
                    )  # remove annoying white space characters
            self.output.append(inLine)
        self.fPtr.close()
        return self.output

    @staticmethod
    def substitute_macros(macro_dict, text):
        """Expands any macros defined by 'macro_dict' in the given 'text'.
        The expanded text is returned."""
        out_text = text
        sorted_macros = [(len(x), x) for x in macro_dict.keys()]
        sorted_macros.sort()
        sorted_macros.reverse()
        for macro in sorted_macros:
            out_text = out_text.replace(macro[1], macro_dict[macro[1]])
        return out_text

    def saveOutput(self, outputFile=None):
        """Writes the processed output to the specified file."""
        if outputFile:
            try:
                self.oPtr = open(outputFile, "w")
            except OSError:
                log.error("Error: Could not open output file for write access.")
                return None

        if self.oPtr:
            for line in self.output:
                self.oPtr.write(line + "\n")
            self.oPtr.close()
        else:
            for line in self.output:
                print(line)
        return 0


# \file
# \section License
# Author: Diamond Light Source, Copyright 2011
#
# 'dls_pmaclib' is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# 'dls_pmaclib' is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with 'dls_pmaclib'.  If not, see http://www.gnu.org/licenses/.
