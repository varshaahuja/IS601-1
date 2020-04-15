import enum
from datetime import datetime, timedelta
import random

import names
from werkzeug.utils import cached_property

from app import db
from auth.models import User
from resources.models import Resource


"""class GatherType(enum.Enum):
    WOOD = 1  # woodcutter
    ORE = 2  # miner
    INGOT = 3  # smelter
"""

class Gender(enum.Enum):
    MALE = 1
    FEMALE = 2

    def __str__(self):
        return self.name  # value string

    def __html__(self):
        return self.value  # label string


class Health(enum.Enum):
    Dead = 0
    Dying = 1
    Sick = 2
    Exhausted = 3
    Ok = 4
    Healthy = 5

    def __str__(self):
        return self.name  # value string

    def __html__(self):
        return self.value  # label string


class Promotion(enum.Enum):
    NONE = 0
    INCREASED_SKILL = 1
    MAXED_SKILL = 2
    INCREASED_EFFICIENCY = 3
    MAXED_EFFICIENCY = 4


class Worker(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(30))
    skill = db.Column(db.Float)
    efficiency = db.Column(db.Float)
    proficiency_wood = db.Column(db.Float, default=0.05)
    proficiency_ore = db.Column(db.Float, default=0.05)
    proficiency_ingot = db.Column(db.Float, default=0.05)
    prof_wood_next_level = db.Column(db.SMALLINT, default=0)
    prof_ore_next_level = db.Column(db.SMALLINT, default=0)
    prof_ingot_next_level = db.Column(db.SMALLINT, default=0)  # smelting
    learning_speed = db.Column(db.SMALLINT, default=5)
    created = db.Column(db.DateTime, default=datetime.utcnow())
    modified = db.Column(db.DateTime, default=datetime.utcnow(), onupdate=datetime.utcnow())
    next_action = db.Column(db.DateTime, default=datetime.utcnow())
    gender = db.Column(db.Enum(Gender))
    cooldown = db.Column(db.SMALLINT, default=1)
    temp_uses = db.Column(db.SMALLINT, default=0)
    lifetime_uses = db.Column(db.Integer, default=0)
    health = db.Column(db.Enum(Health), default=Health.Healthy)
    stamina = db.Column(db.SMALLINT, default=100)  # 0 - 100, made better with food
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user = db.relationship('User')
    previous_user_id = db.Column(db.Integer)  # doesn't need to be a FK, db.ForeignKey('user.id'))

    promote_cost = db.Column(db.Integer, default=0)
    promote_base = db.Column(db.Integer, default=0)

    assigned_to_smelter = db.Column(db.Integer, default=0)
    smelter = db.relationship('Smelter')

    def get_promote_cost(self):
        if self.promote_cost == 0 or self.promote_cost is None:
            if self.promote_base == 0 or self.promote_base is None:
                self.promote_base = int(random.uniform(5, 50))
            self.promote_cost = self.promote_base
            db.session.commit()
        return int(self.promote_cost)

    def __determine_promotion(self):
        choices = []
        if self.skill < 1.0:
            choices.append('skill')
        if self.efficiency < 1.0:
            choices.append('ef')
        if len(choices) > 0:
            choice = random.choices(choices)[0]
            if choice == 'skill':
                self.skill += 0.1
                if self.skill > 1.0:
                    self.skill = 1.0
                    return Promotion.MAXED_SKILL
                else:
                    return Promotion.INCREASED_SKILL
            elif choice == 'ef':
                self.efficiency += 0.1
                if self.efficiency > 1.0:
                    self.efficiency = 1.0
                    return Promotion.MAXED_EFFICIENCY
                else:
                    return Promotion.INCREASED_EFFICIENCY
        return Promotion.NONE

    def promote(self, free=False):
        if (self.user.get_coins() >= self.promote_cost) or free:
            # do promote
            promo = self.__determine_promotion()
            if promo is not Promotion.NONE:
                # cache cost
                cost = self.get_promote_cost()
                # raise the price
                self.promote_cost = self.promote_base * (self.skill+self.efficiency)
                # self.promote_cost += self.promote_cost * 2
                # self.promote_cost = int((self.promote_cost * self.promote_cost) *.5)
                # deduct the cached cost
                if not free:
                    self.user.inventory.update_coins(-cost)
                db.session.commit()
                # succeeded in promote
            # failed to promote
            return promo
        # user can't afford
        return False

    def generate(self, user_id):
        self.skill = random.uniform(0.1, 1.0)
        self.efficiency = random.uniform(0.1, 1.0)
        if bool(random.getrandbits(1)):
            self.gender = Gender.MALE
            self.name = names.get_first_name(gender='male')
        else:
            self.gender = Gender.FEMALE
            self.name = names.get_first_name(gender='female')
        self.user_id = user_id
        self.promote_base = int(random.uniform(5, 50))
        self.previous_user_id = User.get_sys_user_id
        # random proficiencies
        self.proficiency_wood = random.uniform(0.0, 1.0)
        self.proficiency_ore = random.uniform(0.0, 1.0)
        self.proficiency_ingot = random.uniform(0.0, 1.0)
        # determine learning speed (smaller is better)
        self.learning_speed = random.randint(50, 1000)
        print('Saved to user: ' + str(user_id))
        db.session.add(self)
        db.session.commit()

    def offer_transfer(self):
        # auctioned workers have a ref to previous user so they get commission
        user_id = User.get_sys_user_id
        previous = self.user_id
        self.user_id = user_id
        self.previous_user_id = previous
        db.session.commit()

    def fire(self):
        # for fired workers set previous id to System so previous owner doesn't get credit
        user_id = User.get_sys_user_id
        self.user_id = user_id
        self.previous_user_id = user_id
        db.session.commit()

    def can_gather(self):
        if self.assigned_to_smelter is not None:
            if self.assigned_to_smelter > 0:
                if self.smelter is not None:
                    if not self.smelter.unassign(self):
                        # if unassign is True that means we're still working so we can't
                        # do two jobs at once, sorry
                        return False
        if datetime.utcnow() >= self.next_action:
            return True
        return False

    def reset_temp_uses(self):
        self.temp_uses = 0
        db.session.commit()

    def did_gather(self):
        if self.can_gather():
            self.temp_uses += 1
            self.lifetime_uses += 1
            self.next_action = datetime.utcnow() + timedelta(minutes=(self.cooldown*self.temp_uses))
            db.session.commit()

    def __calc_skill(self):
        r = random.uniform(0.0, 1.0)
        n = 1
        if r <= self.skill:
            n = 2
        return n

    @staticmethod
    def __calc_with_efficiency(ef, n):
        r = random.uniform(0.0, 1.0)
        if r <= ef:
            n *= 2
        else:
            # severe penalty of being unhealthy
            if ef < .25:
                n = 0
            # penalty of being unhealthy
            elif ef < .5:
                n -= 1
            # chance of penalty for not being in good health
            elif ef < .75:
                r = random.randint(0, 1)
                if r == 0:
                    n -= 1
        return n

    @staticmethod
    def __calc_bonus(ef, skill, n):
        if ef >= 1.0 and skill >= 1.0:
            n += 1
        return n

    def calc_gather(self, resource):
        ef = self.__get_efficiency()
        # see if we get a bonus item
        n = self.__calc_skill()
        # check if we get any efficiency bonus
        n = self.__calc_with_efficiency(ef, n)
        # max ef and skill reward a bonus
        n = self.__calc_bonus(ef, self.skill, n)

        if n < 0:
            n = 0
            # don't bother calculating further
            return n
        # passed skill/ef check, calc extra and reward worker
        # legacy init proficiency if none
        if self.proficiency_wood is None:
            self.proficiency_wood = random.uniform(0.0, 1.0)
            db.session.commit()
        if self.proficiency_ore is None:
            self.proficiency_ore = random.uniform(0.0, 1.0)
            db.session.commit()
        if self.proficiency_ingot is None:
            self.proficiency_ingot = random.uniform(0.0, 1.0)
            db.session.commit()
        # factor in proficiency
        if resource.is_wood():
            n = int(n * self.proficiency_wood)
        elif resource.is_ore():
            n = int(n * self.proficiency_ore)
        elif resource.is_ingot():
            n = int(n * self.proficiency_ingot)
        # give at least 1 resource since worker passed the skill check before the proficiency
        # assume even the worst ability can get 1 resource
        if n < 1:
            n = 1
        # see if worker increases their proficiency
        self.__check_proficiency_increase(resource, n)
        return n  # ef * self.skill

    def __check_proficiency_increase(self, resource, amount_gathered):
        # legacy for miners that don't have a value
        if self.learning_speed is None:
            # determine learning speed (smaller is better)
            self.learning_speed = random.randint(50, 1000)
        if self.prof_ingot_next_level is None:
            self.prof_ingot_next_level = self.learning_speed
        if self.prof_ore_next_level is None:
            self.prof_ore_next_level = self.learning_speed
        if self.prof_wood_next_level is None:
            self.prof_wood_next_level = self.learning_speed
        # end legacy stuff
        # based on resource deduct from our learning requirement

        # to see if worker increases their proficiency, then reset the learning requirement
        if resource.is_wood():
            self.prof_wood_next_level -= amount_gathered
            if self.prof_wood_next_level <= 0:
                self.proficiency_wood += 0.01
                self.prof_wood_next_level = self.learning_speed
        elif resource.is_ore():
            self.prof_ore_next_level -= amount_gathered
            if self.prof_ore_next_level <= 0:
                self.proficiency_ore += 0.01
                self.prof_ore_next_level = self.learning_speed
        elif resource.is_ingot():
            self.prof_ingot_next_level -= amount_gathered
            if self.prof_ingot_next_level <= 0:
                self.proficiency_ingot += 0.01
                self.prof_ingot_next_level = self.learning_speed

    def __get_efficiency(self):
        if self.health.value < Health.Sick.value:
            return 0
        if self.health == Health.Sick:
            return self.efficiency - (self.efficiency * .75)
        if self.health == Health.Exhausted:
            return self.efficiency - (self.efficiency * .5)
        if self.health == Health.Ok:
            return self.efficiency
        if self.health == Health.Healthy:
            return self.efficiency + (self.efficiency * .1)

    def eat(self, food_increment):
        self.stamina += food_increment
        if self.stamina > 100:
            self.stamina = 100
        db.session.commit()

    def use_stamina(self, decrement=5):
        self.stamina -= decrement
        db.session.commit()

    def remove_from_smelter(self):
        self.assigned_to_smelter = 0
        self.smelter = None
