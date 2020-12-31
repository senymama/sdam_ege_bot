import pymysql
from pymysql.cursors import DictCursor
import time
import json
import logging
import config

logging.basicConfig(level=logging.INFO)
log = logging.getLogger('bot_db')


class BotDB:
    def __init__(self):
        """Status definition:
        0 waiting for name
        1 waiting for task
        """
        self.connection = pymysql.connect(
            host=config.host,
            user=config.user,
            password=config.password,
            db=config.db,
            charset=config.charset,
            cursorclass=DictCursor
        )
        self.cursor = self.connection.cursor()
        timeout = 2147482
        self.cursor.execute(query=f"""SET SESSION wait_timeout := {timeout};""")
        self.connection.commit()
        # TODO Add logging

    def add_user(self, user_id):
        q = f"""
                INSERT INTO users(user_id, reg_time)
                VALUES ({user_id}, {time.time()})
            """
        self.cursor.execute(q)
        self.connection.commit()
        log.info(f"User [ID: {user_id}]: create account")

    def change_user_status(self, user_id, new_status):
        q = f"""
                UPDATE users
                SET status = {new_status}
                WHERE user_id = {user_id}
            """
        self.cursor.execute(q)
        self.connection.commit()
        log.info(f"User [ID: {user_id}]: change status")

    def set_user_name(self, user_id, name):
        q = f"""
                UPDATE users
                SET name = '{name}'
                WHERE user_id = {user_id}
            """
        self.cursor.execute(q)
        self.change_user_status(user_id=user_id, new_status=1)
        self.connection.commit()
        log.info(f"User [ID: {user_id}]: change name")

    def add_new_solved_problem(self, user_id, task_id, cost=1):
        """Cost - how mach point should we pay for this problem"""
        cur = self.connection.cursor()

        # At first get solved problems array
        data = self.get_user_data(user_id)
        score, solved_problems = data["score"], data["solved_problems"]

        if solved_problems == "":  # If this user have never asked
            solved_problems = repr([task_id])
        else:
            s_p_list = json.loads(solved_problems)
            s_p_list.append(task_id)
            solved_problems = repr(s_p_list)

        add_point_q = f"""
                        UPDATE users
                        SET score = {score + cost}, solved_problems = '{solved_problems}'
                        WHERE user_id = {user_id}
                        """
        cur.execute(add_point_q)
        self.connection.commit()
        return score + cost

    def add_new_wrong_solved_problem(self, user_id, task_id, cost = 0):
        cur = self.connection.cursor()

        # At first get unsolved problems array
        data = self.get_user_data(user_id)
        score, wrong_solved = data["score"], data["wrong_solved"]

        if wrong_solved == "":
            wrong_solved = repr([task_id])
        else:
            s_p_list = json.loads(wrong_solved)
            s_p_list.append(task_id)
            wrong_solved = repr(s_p_list)

        add_w_solved_query = f"""UPDATE users SET score = {score + cost}, wrong_solved = '{wrong_solved}'"""
        cur.execute(add_w_solved_query)
        self.connection.commit()
        return score + cost

    def set_current_problem(self, user_id: int, current_task_id: int):
        q = f"""
            UPDATE users
            SET current_problem_id = {current_task_id}
            WHERE user_id = {user_id}
        """
        self.cursor.execute(q)
        self.connection.commit()

    def get_top_users(self):
        q = f"""
                SELECT * from users
                WHERE status != 0
                ORDER BY score DESC
                LIMIT 15
            """
        cur = self.connection.cursor()
        cur.execute(query=q)
        return cur.fetchall()

    def get_user_data(self, user_id):
        q = f"""
                SELECT * FROM users
                WHERE user_id = {user_id}
            """
        cur = self.connection.cursor()
        cur.execute(q)
        return cur.fetchone()

    def delete_user(self, user_id):
        q = f"""DELETE from users
                WHERE user_id = {user_id}
            """
        self.cursor.execute(q)
        self.connection.commit()

    def get_user_score_solved_problems(self, user_id):
        cur = self.connection.cursor()
        q = f"""SELECT solved_problems, score FROM users WHERE user_id = {user_id}"""
        cur.execute(q)
        data = cur.fetchone()
        solved_problems = data["solved_problems"]
        score = data["score"]
        return score, solved_problems
