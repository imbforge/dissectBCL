#!/package/anaconda3/bin/python3
import argparse
import sys
import smtplib
import os
from dissectBCL.misc import getConf
from email.mime.text import MIMEText
import glob


def fetchFirstNameAndEmail(lastName, config):
    # search in dictionary file defined in config for lastName
    try:
        fn = config['parkour']['userList']
    except KeyError:
        print("Error: fetchFirstNameAndEmail\n\
        No dictionary defined. \
        Specify --toEmail and --toName explicitly!")
        sys.exit(1)

    if not os.path.exists(fn):
        print("{} does not exist!".format(fn))
        sys.exit(1)

    f = open(fn)
    d = dict()
    for line in f:
        cols = line.rstrip().split("\t")

        # only accept format: firstName, lastName, email
        if (len(cols) < 3):
            continue

        # ignore all other lastNames
        if cols[1] != lastName:
            continue

        # check if lastName occurs more than once in list
        if cols[1] in d:
            print("Error: fetchFirstNameAndEmail\n\
            Name {} exists more than once. \
            Specify --toEmail and --toName explicitly!".format(cols[1]))
            print('now:      ', cols[1], cols[0], cols[2])
            print('previous: ', cols[1], d[cols[1]])
            sys.exit(1)

        # add to dictionary
        d[cols[1]] = [cols[0], cols[2]]
    f.close()

    if lastName not in d:
        print("Error: fetchFirstNameAndEmail\n\
    No Information for lastName={}. {} needs update".format(lastName, fn))
        sys.exit(1)

    return d[lastName]


def getProjectIDs(projects, config):
    IDs = []
    for p in projects:
        # Sanity check
        assert (p.startswith("Project_"))
        IDs.append(p.split("_")[1])
        PI = p.split("_")[-1].lower()
    # Get the actual sequencing_data dir
    # Assume if multiple projects are given, they all in the same flowcell.
    flowcell = getFlowCell()
    # Assume that only a flow cell exists only once.
    seqdir = glob.glob(
        os.path.join(
            config['Dirs']['piDir'],
            PI,
            config['Internals']['seqDir'] + '*',
            flowcell
        )
    )[0].split('/')[-2]

    if len(IDs) == 1:
        return IDs[0], seqdir

    return " and ".join([", ".join(IDs[:-1]), IDs[-1]]), seqdir


def getFlowCell():
    return os.path.split(os.getcwd())[-1]


def main():
    parser = argparse.ArgumentParser(
        description="Send an email to one or more users about a project(s) \
             being finished. This must be run in the output directory of the \
            demultiplexing pipeline.")
    parser.add_argument(
        '--configfile',
        default=os.path.expanduser('~/configs/dissectBCL_prod.ini'),
        help='specify a custom ini file. default = {}'.format(
            os.path.expanduser('~/configs/dissectBCL_prod.ini')
        )
    )
    parser.add_argument(
        "--notGood",
        action="store_true",
        help="If specified, \
        do NOT say that the sequencing quality was good."
    )
    parser.add_argument(
        "--analysis",
        action="store_true",
        help="If specified, \
        the BigRedButton did something with these projects."
    )
    parser.add_argument(
        "--cc",
        nargs="+",
        help="One or more addresses to CC."
    )
    parser.add_argument(
        "--comment",
        help="Either comment that will be \
        included as its own paragraph (ensure you quote the whole thing!) or \
        the path to a file containing such a comment."
    )
    parser.add_argument(
        "--fromPerson",
        help="The name of the person sending the email."
    )
    parser.add_argument(
        "--fromEmail",
        help="The email address of the person \
        sending this. Note that they receive a copy as BCC!"
    )
    parser.add_argument(
        "--fromSignature",
        help="An optional signature of the person \
        sending this."
    )
    parser.add_argument(
        "--toEmail",
        help="The email address of the person \
         who will receive this.",
        default=""
    )
    parser.add_argument(
        "--toName",
        help="The name of the person who will \
        receive this.",
        default=""
    )
    parser.add_argument(
        "project",
        nargs="+",
        help="One or more project \
        directories. Only the user on the first will receive an email!"
    )

    args = parser.parse_args()

    print("emailProjectFinished: Loading conf from {}".format(args.configfile))
    config = getConf(args.configfile, quickload=True)

    # Double check the project folder(s) actually exist.
    for p in args.project:
        if not os.path.exists(p):
            sys.exit("Project folder {} not found.".format(p))

    # get lastName (user) from project name
    lastName = args.project[0].split("_")[2]
    if not args.toEmail or not args.toName:
        firstName, email = fetchFirstNameAndEmail(lastName, config)
    else:
        firstName, email = args.toName, args.toEmail

    if not firstName or not email:
        sys.exit("User is not known or does not have an email!\n")

    if not args.fromPerson or not args.fromEmail:
        sys.exit("Sender is not known or does not have an email!\n")

    content = """Hi {},

Your sequencing samples for project""".format(firstName)

    if len(args.project) > 1:
        content += "s"
    content += (" {} are finished and the results are now available in your "
                "group's {} directory"
                .format(
                    getProjectIDs(args.project, config)[0],
                    getProjectIDs(args.project, config)[1])
                )

    content += " under the {} folder.\n".format(getFlowCell())

    if not args.notGood:
        content += "The overall sequencing quality for these samples was good."

    if args.analysis:
        content += (
            "\nAn automated partial analysis "
            "(https://doi.org/10.1093/bioinformatics/btz436) "
            "is available in the same location. \nIf you would like completed "
            "analysis in a semi-automated fashion, please request that using "
            "our online portal: http://snakequest.ie-freiburg.mpg.de .\n"
            )

    content += (
        "\nPlease note that sequencing data is no longer deposited "
        "into Galaxy by default. If you need to access this data in Galaxy, "
        "please let me know. \n"
    )

    if args.comment:
        content += "\n===\n"
        if os.path.exists(args.comment):
            content += open(args.comment).read()
        else:
            content += args.comment
        content += "\n===\n"

    content += "\nPlease let me know if you have any other questions,\
        \n{}\n".format(args.fromPerson)

    # Add a .signature
    if args.fromSignature is not None and os.path.exists(args.fromSignature):
        content += "\n--\n"
        content += open(args.fromSignature).read()

    # Send the Email
    msg = MIMEText(content)
    msg['Subject'] = "Sequencing samples ready - " + args.project[0]
    msg['From'] = args.fromEmail
    msg['To'] = email
    bioinfo_cc = config['communication']['bioinfoCore']
    host = config['communication']['host']

    if args.cc:
        msg['Cc'] = ", ".join(args.cc)

    msg['Bcc'] = bioinfo_cc

    s = smtplib.SMTP(host)
    s.send_message(msg)
    s.quit()


if __name__ == "__main__":
    if len(sys.argv) == 1:
        sys.argv.append("--help")
    main(sys.argv[1:])
