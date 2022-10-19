import logging
import requests
from typing import Final
from datetime import date, timedelta
from bs4 import BeautifulSoup

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s", level=logging.INFO
)

MONTH_INTERVAL: Final = "m"
DAY_INTERVAL: Final = "d"
HOUR_INTERVAL: Final = "h"
FIFTEEN_MINUTE_INTERVAL: Final = "mi"

class Evergy:
    def __init__(self, username, password, account_num, premise_id = None):
        self.logged_in = False
        self.session = None
        self.username = username
        self.password = password
        self.account_number = account_num
        self.premise_id = premise_id
        self.login_url = "https://www.evergy.com/log-in"
        self.logout_url = "https://www.evergy.com/logout"
        self.account_summary_url = (
            "https://www.evergy.com/ma/my-account/account-summary"
        )
        self.account_dashboard_url = (
            "https://www.evergy.com/api/account/{accountNum}/dashboard/current"
        )
        self.usageDataUrl = "https://www.evergy.com/api/report/usage/{premise_id}?interval={interval}&from={start}&to={end}"

    def login(self):
        """
        Log in to the customer portal and load the first premise if one wasn't supplied in the config
        """
        self.session = requests.Session()
        logging.info("Logging in with username: " + self.username)

        # Evergy does not offer a login API enpoint, so we're forced to use the login form
        login_form = self.session.get(self.login_url)
        login_form_soup = BeautifulSoup(login_form.text, "html.parser")
        csrf_token = login_form_soup.select(".login-form > input")[0]["value"]
        csrf_token_name = login_form_soup.select(".login-form > input")[0]["name"]

        login_payload = {
            "Username": str(self.username),
            "Password": str(self.password),
            csrf_token_name: csrf_token,
        }

        r = self.session.post(
            url=self.login_url, data=login_payload, allow_redirects=False
        )

        logging.info("Login response: " + str(r.status_code))
        r = self.session.get(self.account_summary_url)
        self.logged_in = r.status_code == 200

        if not self.logged_in:
            raise Exception("Login error. Check credentials and account number", r)
        else:
            logging.info("Account summary response: " + str(r.status_code))
            
            if self.premise_id is None:
                first_premise = self.get_premises()[0]
                self.premise_id = first_premise["premise_id"]
            
            self.logged_in = (
                self.account_number is not None and self.premise_id is not None
            )

    def logout(self):
        """
        Logout out the customer portal
        """
        logging.info("Logging out")
        self.session.get(url=self.logout_url)
        self.session = None
        self.logged_in = False

    def get_premises(self) -> list[dict]:
        """
        Gets the premises assoctiate with the given account number
        :rtype: [dict]
        """
        logging.info("Getting Premises")

        if not self.logged_in:
            self.login()
        
        dashboard_data = self.session.get(
            self.account_dashboard_url.format(accountNum=self.account_number)
        ).json()
        
        premises_data = dashboard_data["addresses"]

        return [{"premise_id": address["premiseId"], "address": address["street"]} for address in premises_data]


    def get_usage(self, days: int = 1, interval: str = DAY_INTERVAL) -> list[dict]:
        """
        Gets the energy usage for previous days up until today. Useful for getting the most recent data.
        :rtype: [dict]
        :param days: The number of days back to get data for.
        :param interval: The time period between each data element in the returned data. Default is days.
        :return: A list of usage elements. The number of elements will depend on the `interval` argument.
        """
        start_date = date.today() - timedelta(days=days)
        return self.get_usage_range(start_date, date.today(), interval=interval)

    def get_usage_range(self, start: date = date.today(), end: date = date.today(),
            interval: str = DAY_INTERVAL) -> list[dict]:
        """
        Gets a specific range of historical usage. Could be useful for reporting.
        :param start: The date to begin getting data for (inclusive)
        :param end: The last date to get data for (inclusive)
        :param interval: The time period between each data element in the returned data. Default is days.
        :return: A list of usage elements. The number of elements will depend on the `interval` argument.
        """
        if not self.logged_in:
            self.login()
        
        if start > end:
            logging.error("'start' date can't be after 'end' date")
            raise Exception("'start' date can't be after 'end' date")
        
        logging.info("Getting Usage: " + str(start) + " - " + str(end))

        url = self.usageDataUrl.format(
            premise_id=self.premise_id, interval=interval, start=start, end=end
        )
        logging.info("Fetching {}".format(url))
        usage_response = self.session.get(url)
        # A 403 is return if the user got logged out from inactivity
        if self.logged_in and usage_response.status_code == 403:
            logging.info("Received HTTP 403, logging in again")
            self.login()
            usage_response = self.session.get(url)
        if usage_response.status_code != 200:
            raise Exception("Invalid login credentials")
        return usage_response.json()["data"]
