import common from './common';
import Admin from './admin';
import Backoffice from './backoffice';
import MyLab from './mylab';
import ProfessionalTravel from './professionaltravel';
import Infrastructure from './infrastructure';
import EquipmentElectricConsumption from './equipmentelectricconsumption';
import Purchase from './purchase';
import InternalServices from './internalservices';
import ExternalCloud from './externalcloud';

const modules = [
  common,
  Admin,
  Backoffice,
  MyLab,
  ProfessionalTravel,
  Infrastructure,
  EquipmentElectricConsumption,
  Purchase,
  InternalServices,
  ExternalCloud,
];

type Lang = 'en' | 'fr';

const extract = (lang: Lang) => {
  const messages: Record<string, string> = {};
  modules.forEach((mod) => {
    // The modules are imported directly as objects because they use export default
    const content = mod;
    Object.keys(content).forEach((key) => {
      // @ts-ignore
      if (content[key] && content[key][lang]) {
        // @ts-ignore
        messages[key] = content[key][lang];
      }
    });
  });
  return messages;
};

export default {
  'en-US': extract('en'),
  'fr-CH': extract('fr'),
};
