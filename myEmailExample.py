import os

# Set environment variables

# You'll need a Gmail address and an 'app password' to send emails.
#
# See this article from Google for more information:
# https://support.google.com/accounts/answer/185833?hl=en
#
# Note that Google does not recommend the use of 'app passwords' 
# and can sometimes change how they work.

def setVar():
    os.environ['EMAIL_TO'] = 'yourname@domain.com'
    os.environ['EMAIL_FROM'] = 'yourname@domain.com'
    os.environ['EMAIL_FROM_PASSWORD'] = 'yourpassword'
