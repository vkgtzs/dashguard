import unittest
from imu_segura import IMUSegura, CAMPOS


class Bus:
    def __init__(self):
        self.regs={0x75:0x68,0x6B:0,0x1B:0,0x1C:0}
        self.datos=[0,0,0,0,0x40,0,0,0,0,131,0,0,0,0]
        self.error=False
        self.escrituras=[]
    def write_byte_data(self,d,r,v):
        self.regs[r]=v; self.escrituras.append((r,v))
    def read_byte_data(self,d,r):
        if self.error: raise OSError('I2C no disponible')
        return self.regs[r]
    def read_i2c_block_data(self,d,r,n): return self.datos[:]


class IMU(unittest.TestCase):
    def preparar(self):
        bus=Bus(); imu=IMUSegura(bus)
        imu.inicializar(muestras=2,esperar=lambda _:None)
        return bus,imu

    def test_lectura_valida_y_calibracion(self):
        _,imu=self.preparar()
        m=imu.leer()
        self.assertTrue(m['imu_valida'])
        self.assertAlmostEqual(m['magnitud_ms2'],9.80665)
        self.assertEqual(m['gx_grados_s'],0)

    def test_ceros_suspension_y_error_no_fabrican_medidas_ni_recuperan_oculto(self):
        for tipo in ('ceros','suspension','i2c','rango'):
            bus,imu=self.preparar()
            originales=len(bus.escrituras)
            if tipo=='ceros': bus.datos=[0]*14
            elif tipo=='suspension': bus.regs[0x6B]=0x40
            elif tipo=='rango': bus.regs[0x1C]=0x08
            else: bus.error=True
            muestra={**imu.leer(),'gps_valido':True,'latitud':1.0}
            self.assertFalse(muestra['imu_valida'])
            self.assertTrue(all(muestra[c] is None for c in CAMPOS))
            self.assertTrue(muestra['gps_valido'])
            bus.regs[0x6B]=0; bus.regs[0x1C]=0; bus.error=False
            self.assertFalse(imu.leer()['imu_valida'])
            self.assertEqual(len(bus.escrituras),originales)

    def test_error_inicializacion_no_da_offsets(self):
        bus=Bus(); bus.error=True; imu=IMUSegura(bus)
        imu.inicializar(muestras=2,esperar=lambda _:None)
        self.assertFalse(imu.leer()['imu_valida'])
        self.assertIsNone(imu.offsets)


if __name__=='__main__': unittest.main()
