"""Emission type model for categorizing different types of emissions."""

from enum import Enum


class EmissionTypeEnum(int, Enum):
    energy = 1
    equipment = 2
    food = 3
    waste = 4
    commuting = 5
    grey_energy = 6
    plane = 7
    train = 8
    car = 9
    # External Clouds:
    # cloud storage
    stockage = 10
    # cloud virtualisation
    virtualisation = 11
    # cloud compute
    calcul = 12
    # External AI:
    ai_provider = 13
